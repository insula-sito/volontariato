"""Punto di ingresso: python -m baltic_watch [--dry-run] [--year 2026] [--source eyp] [--weekly]"""
from __future__ import annotations

import argparse
import logging
import sys
from collections import Counter
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from .config import ROOT, load_config
from .dedupe import keys_for, merge
from .filters import BREVI, evaluate
from .http import PoliteSession
from .models import Listing
from .notify import Notifier, format_digest, format_new, format_weekly
from .scoring import score
from .sources import SOURCES
from .state import State

ROME = ZoneInfo("Europe/Rome")
STATE_PATH = ROOT / "data" / "seen.json"
DIGEST_THRESHOLD = 10  # oltre questo numero di nuovi annunci, un solo messaggio riassuntivo
log = logging.getLogger("baltic_watch")


def default_year(today: date) -> int:
    return today.year + 1 if today > date(today.year, 9, 10) else today.year


def scheduled_slot_ok(cron: str) -> bool:
    """GitHub usa l'ora UTC: il workflow parte alle 05:00 e alle 06:00 UTC e
    qui teniamo solo l'esecuzione che corrisponde alle 07:00 di Roma
    (05 UTC con l'ora legale, 06 UTC con l'ora solare)."""
    hour = int(cron.split()[1])
    offset = datetime.now(ROME).utcoffset()
    expected = 7 - int(offset.total_seconds() // 3600)
    return hour == expected


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="baltic_watch",
                                description="Opportunità di volontariato nei Paesi baltici → Telegram")
    p.add_argument("--dry-run", action="store_true", help="stampa i risultati, non invia e non salva lo stato")
    p.add_argument("--year", type=int, help="anno target (default: la prossima estate)")
    p.add_argument("--source", action="append", choices=sorted(SOURCES), help="solo queste fonti (ripetibile)")
    p.add_argument("--weekly", action="store_true", help="invia/stampa anche il riepilogo settimanale")
    p.add_argument("--schedule", help="espressione cron che ha avviato il workflow (uso interno)")
    p.add_argument("--state", type=Path, default=STATE_PATH, help="percorso del file di stato")
    p.add_argument("-v", "--verbose", action="store_true", help="mostra anche gli annunci scartati")
    return p.parse_args(argv)


def run(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(levelname)s %(name)s: %(message)s")
    today = datetime.now(ROME).date()

    if args.schedule and not scheduled_slot_ok(args.schedule):
        log.info("Esecuzione programmata '%s' non corrisponde alle 7:00 di Roma: salto.", args.schedule)
        return 0

    year = args.year or default_year(today)
    cfg = load_config(year)
    win_start, win_end = cfg.window()
    historical = win_end < today
    dry_run = args.dry_run
    if historical and not dry_run:
        log.warning("Anno %s già passato: modalità di prova, forzo --dry-run.", year)
        dry_run = True

    state = State(args.state)
    if args.schedule and state.data.get("ultima_esecuzione") == today.isoformat():
        log.info("Già eseguito oggi: salto.")
        return 0

    notifier = Notifier(dry_run=dry_run)
    http = PoliteSession()
    names = args.source or list(SOURCES)
    print(f"Anno target {year}: periodo {win_start:%d/%m}–{win_end:%d/%m/%Y}"
          f"{' (modalità storica)' if historical else ''}. Fonti: {', '.join(names)}")

    # 1. Scarica da tutte le fonti
    sources = {}
    listings: list[Listing] = []
    alerts: list[str] = []
    for name in names:
        src = SOURCES[name](http, cfg, today, historical)
        sources[name] = src
        error = None
        try:
            got = src.fetch()
            listings.extend(got)
            print(f"  • {src.label}: {src.raw_count} elementi letti, {len(got)} annunci baltici")
        except Exception as exc:  # una fonte rotta non deve fermare le altre
            error = f"{type(exc).__name__}: {exc}"[:200]
            log.error("Fonte %s in errore: %s", name, error)
            print(f"  • {src.label}: ERRORE {error}")
        if not dry_run:
            msg = state.record_health(name, ok=error is None, count=src.raw_count, error=error, today=today)
            if msg:
                alerts.append(msg)

    # 2. Filtri sui singoli annunci; i nuovi che passano vengono arricchiti
    discarded: Counter[str] = Counter()
    kept: list[Listing] = []
    for item in listings:
        v = evaluate(item, cfg, today, historical)
        if not v.keep:
            discarded[v.motivo_scarto.split(" (")[0]] += 1
            log.debug("Scartato [%s] %s — %s", v.motivo_scarto, item.titolo, item.url)
            continue
        if state.find({f"id:{item.id}"}) is None:
            try:
                sources[item.fonte].enrich(item)
            except Exception as exc:
                log.warning("Arricchimento fallito per %s: %s", item.url, exc)
        kept.append(item)

    # 3. Deduplica, nuova valutazione, punteggio, stato
    new_entries: list[dict] = []
    results: list[tuple[dict, bool]] = []
    for item in merge(kept):
        v = evaluate(item, cfg, today, historical)
        if not v.keep:
            continue
        pts, why = score(item, cfg)
        keys = keys_for(item)
        is_new = state.upsert(item, keys, pts, why, v.sezione, v.avvisi, today)
        key = state.find(keys)
        entry = state.annunci[key]
        results.append((entry, is_new))
        if is_new:
            new_entries.append(entry)

    # 4. Output
    results.sort(key=lambda r: -r[0]["punteggio"])
    main_ = [e for e, _ in results if e["sezione"] != BREVI]
    short = [e for e, _ in results if e["sezione"] == BREVI]
    print(f"\nAnnunci idonei: {len(results)} ({len(main_)} principali, {len(short)} brevi), "
          f"nuovi: {len(new_entries)}. Scartati: {sum(discarded.values())}"
          + (f" — {dict(discarded)}" if discarded else ""))
    if dry_run:
        for title, group in (("PRINCIPALI", main_), ("BREVI, COMBINABILI", short)):
            if group:
                print(f"\n=== {title} ===")
            for e in group:
                print(f"[{e['punteggio']:3d}] {e['paese']} {e['titolo']}\n"
                      f"      {e.get('organizzazione') or '-'} · {e.get('inizio')}→{e.get('fine')} "
                      f"({e.get('durata') or '?'} gg) · scad. {e.get('scadenza') or '-'}\n"
                      f"      {e['motivo']}\n"
                      + (f"      ⚠ {'; '.join(e['avvisi'])}\n" if e.get("avvisi") else "")
                      + f"      {e['url']}")

    new_entries.sort(key=lambda e: -e["punteggio"])
    if len(new_entries) > DIGEST_THRESHOLD:
        for msg in format_digest(new_entries, cfg.paesi, f"🆕 {len(new_entries)} nuovi annunci"):
            notifier.send(msg)
    else:
        for e in new_entries:
            notifier.send(format_new(e, cfg.paesi))
    for msg in alerts:
        notifier.send(msg)

    is_monday = today.weekday() == 0
    if args.weekly or (args.schedule and is_monday and state.data.get("ultimo_riepilogo") != today.isoformat()):
        entries = state.open_entries(today) if not historical else [e for e, _ in results]
        for msg in format_weekly(entries, cfg.paesi, today, cfg.filters["scadenze_evidenza_giorni"]):
            notifier.send(msg)
        if not dry_run:
            state.data["ultimo_riepilogo"] = today.isoformat()

    for src in sources.values():
        try:
            src.finish(save=not dry_run)
        except Exception as exc:
            log.warning("Chiusura della fonte %s non riuscita: %s", src.name, exc)

    if not dry_run:
        state.data["ultima_esecuzione"] = today.isoformat()
        state.prune(today)
        state.save()
        print(f"Stato salvato in {args.state}")
    return 0


if __name__ == "__main__":
    sys.exit(run())
