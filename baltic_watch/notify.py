"""Messaggi Telegram (o stampa a schermo con --dry-run)."""
from __future__ import annotations

import html
import logging
import os
import time
from datetime import date

import requests

from .filters import BREVI
from .models import format_range

log = logging.getLogger(__name__)
TELEGRAM_LIMIT = 4000


def esc(value) -> str:
    return html.escape(str(value)) if value is not None else ""


def _flag(paesi: dict, code: str | None) -> str:
    info = paesi.get(code or "", {})
    return f"{info.get('bandiera', '')} {info.get('nome', code or '?')}".strip()


def _d(iso: str | None) -> str:
    return date.fromisoformat(iso).strftime("%d/%m/%Y") if iso else "non indicata"


def format_new(entry: dict, paesi: dict) -> str:
    start = date.fromisoformat(entry["inizio"]) if entry.get("inizio") else None
    end = date.fromisoformat(entry["fine"]) if entry.get("fine") else None
    durata = f" ({entry['durata']} gg)" if entry.get("durata") else ""
    head = "🧩 <i>Breve, combinabile</i>\n" if entry.get("sezione") == BREVI else ""
    lines = [
        f"{head}🆕 <b>{esc(entry['titolo'])}</b>",
        f"🏢 {esc(entry.get('organizzazione') or 'organizzazione non indicata')} · {_flag(paesi, entry.get('paese'))}",
        f"📅 {format_range(start, end)}{durata}",
        f"⏳ Scadenza: {_d(entry.get('scadenza'))}",
        f"⭐ <b>{entry['punteggio']}/100</b> — {esc(entry['motivo'])}",
    ]
    if entry.get("avvisi"):
        lines.append("⚠️ " + esc("; ".join(entry["avvisi"])))
    lines.append(f"🔗 {esc(entry['url'])}")
    return "\n".join(lines)


def format_digest(entries: list[dict], paesi: dict, title: str) -> list[str]:
    """Elenco compatto (usato per il primo avvio con molti annunci)."""
    rows = [f"<b>{esc(title)}</b>"]
    for e in entries:
        start = date.fromisoformat(e["inizio"]) if e.get("inizio") else None
        end = date.fromisoformat(e["fine"]) if e.get("fine") else None
        rows.append(f"• <b>{e['punteggio']}</b> {_flag(paesi, e.get('paese'))} "
                    f"<a href=\"{esc(e['url'])}\">{esc(e['titolo'])}</a> — {format_range(start, end)}")
    return split_messages(rows)


def format_weekly(entries: list[dict], paesi: dict, today: date, giorni_evidenza: int) -> list[str]:
    principali = [e for e in entries if e.get("sezione") != BREVI]
    brevi = [e for e in entries if e.get("sezione") == BREVI]
    rows = [f"📋 <b>Riepilogo settimanale</b> — {today:%d/%m/%Y}",
            f"{len(entries)} annunci ancora aperti. ⏰ = scadenza entro {giorni_evidenza} giorni."]

    def row(e: dict) -> str:
        start = date.fromisoformat(e["inizio"]) if e.get("inizio") else None
        end = date.fromisoformat(e["fine"]) if e.get("fine") else None
        scad = ""
        if e.get("scadenza"):
            sd = date.fromisoformat(e["scadenza"])
            alarm = "⏰ " if (sd - today).days <= giorni_evidenza else ""
            scad = f" · {alarm}scade {sd:%d/%m}"
        return (f"• <b>{e['punteggio']}</b> {_flag(paesi, e.get('paese'))} "
                f"<a href=\"{esc(e['url'])}\">{esc(e['titolo'])}</a> — {format_range(start, end)}{scad}")

    if principali:
        rows.append("\n<b>2-5 settimane</b>")
        rows += [row(e) for e in principali]
    if brevi:
        rows.append("\n<b>Brevi, combinabili</b>")
        rows += [row(e) for e in brevi]
    if not entries:
        rows.append("Nessun annuncio aperto al momento.")
    return split_messages(rows)


def split_messages(rows: list[str]) -> list[str]:
    out, cur = [], ""
    for r in rows:
        if len(cur) + len(r) + 1 > TELEGRAM_LIMIT and cur:
            out.append(cur)
            cur = ""
        cur = f"{cur}\n{r}" if cur else r
    if cur:
        out.append(cur)
    return out


class Notifier:
    def __init__(self, dry_run: bool):
        self.dry_run = dry_run
        self.token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
        self.chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
        if not dry_run and not (self.token and self.chat_id):
            raise SystemExit("TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID non impostati "
                             "(usa --dry-run per provare senza inviare).")

    def send(self, text: str) -> None:
        if self.dry_run:
            print("\n----- [messaggio Telegram, non inviato] -----")
            print(text)
            return
        try:
            r = requests.post(
                f"https://api.telegram.org/bot{self.token}/sendMessage",
                data={"chat_id": self.chat_id, "text": text, "parse_mode": "HTML",
                      "disable_web_page_preview": "true"},
                timeout=30,
            )
        except requests.RequestException as exc:
            # l'eccezione originale contiene l'URL con il token: non la propaghiamo
            raise RuntimeError(f"Errore di rete verso Telegram ({type(exc).__name__})") from None
        if r.status_code == 429:
            wait = r.json().get("parameters", {}).get("retry_after", 5)
            time.sleep(wait)
            return self.send(text)
        if not r.ok:
            # non stampiamo l'URL: contiene il token
            # niente raise_for_status(): il messaggio d'errore conterrebbe l'URL con il token
            raise RuntimeError(f"Invio Telegram fallito: HTTP {r.status_code} {r.text[:300]}")
        time.sleep(1.1)  # limite di Telegram: ~1 messaggio al secondo per chat
