"""Stato persistente in data/seen.json: annunci già visti e salute delle fonti.

Si salvano solo i campi utili alle notifiche (niente contatti personali):
il file viene committato in un repository pubblico."""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

from .models import Listing

HEALTH_THRESHOLD = 3


class State:
    def __init__(self, path: Path):
        self.path = path
        if path.exists():
            self.data = json.loads(path.read_text(encoding="utf-8"))
        else:
            self.data = {}
        self.data.setdefault("versione", 1)
        self.data.setdefault("annunci", {})
        self.data.setdefault("salute", {})
        self.data.setdefault("ultima_esecuzione", None)
        self.data.setdefault("ultimo_riepilogo", None)
        self._index: dict[str, str] | None = None

    # --- annunci ----------------------------------------------------------
    @property
    def annunci(self) -> dict[str, dict]:
        return self.data["annunci"]

    def _build_index(self) -> dict[str, str]:
        idx: dict[str, str] = {}
        for key, entry in self.annunci.items():
            for k in entry.get("chiavi", []):
                idx[k] = key
        return idx

    def find(self, keys: set[str]) -> str | None:
        if self._index is None:
            self._index = self._build_index()
        return next((self._index[k] for k in keys if k in self._index), None)

    def upsert(self, listing: Listing, keys: set[str], punteggio: int, motivo: str,
               sezione: str, avvisi: list[str], today: date) -> bool:
        """Registra l'annuncio. Restituisce True se è nuovo."""
        existing = self.find(keys)
        key = existing or listing.id
        entry = self.annunci.get(key, {"primo_avvistamento": today.isoformat()})
        entry.update({
            "titolo": listing.titolo,
            "organizzazione": listing.organizzazione,
            "paese": listing.paese,
            "inizio": listing.inizio.isoformat() if listing.inizio else None,
            "fine": listing.fine.isoformat() if listing.fine else None,
            "durata": listing.durata,
            "scadenza": listing.scadenza.isoformat() if listing.scadenza else None,
            "punteggio": punteggio,
            "motivo": motivo,
            "sezione": sezione,
            "avvisi": avvisi,
            "url": listing.url,
            "fonti": sorted(set(entry.get("fonti", [])) | set(listing.fonti)),
            "chiavi": sorted(set(entry.get("chiavi", [])) | keys),
            "ultimo_avvistamento": today.isoformat(),
        })
        self.annunci[key] = entry
        if self._index is not None:
            for k in entry["chiavi"]:
                self._index[k] = key
        return existing is None

    def open_entries(self, today: date, max_age_days: int = 14) -> list[dict]:
        """Annunci ancora aperti e visti di recente, ordinati per punteggio."""
        out = []
        for entry in self.annunci.values():
            seen = date.fromisoformat(entry["ultimo_avvistamento"])
            if (today - seen).days > max_age_days:
                continue
            if entry.get("scadenza") and date.fromisoformat(entry["scadenza"]) < today:
                continue
            if entry.get("fine") and date.fromisoformat(entry["fine"]) < today:
                continue
            out.append(entry)
        return sorted(out, key=lambda e: -e.get("punteggio", 0))

    def prune(self, today: date, keep_days: int = 400) -> None:
        limit = today - timedelta(days=keep_days)
        for key in [k for k, e in self.annunci.items()
                    if date.fromisoformat(e["ultimo_avvistamento"]) < limit]:
            del self.annunci[key]
        self._index = None

    # --- salute delle fonti -------------------------------------------------
    def record_health(self, source: str, ok: bool, count: int, error: str | None,
                      today: date) -> str | None:
        """Aggiorna i contatori. Restituisce un messaggio di avviso da inviare,
        oppure None. Avvisa una volta al 3° problema di fila e quando la fonte
        torna a funzionare."""
        h = self.data["salute"].setdefault(source, {"problemi_consecutivi": 0, "allertato": False})
        problem = (not ok) or count == 0
        if problem:
            h["problemi_consecutivi"] += 1
            h["ultimo_problema"] = error or "zero risultati"
            h["data_ultimo_problema"] = today.isoformat()
            if h["problemi_consecutivi"] >= HEALTH_THRESHOLD and not h["allertato"]:
                h["allertato"] = True
                return (f"⚠️ La fonte <b>{source}</b> ha problemi da {h['problemi_consecutivi']} "
                        f"esecuzioni di fila ({h['ultimo_problema']}). Probabile cambio del sito.")
            return None
        was_alerted = h.get("allertato")
        h.update({"problemi_consecutivi": 0, "allertato": False,
                  "ultimo_ok": today.isoformat(), "ultimi_risultati": count})
        if was_alerted:
            return f"✅ La fonte <b>{source}</b> funziona di nuovo ({count} risultati)."
        return None

    # --- persistenza --------------------------------------------------------
    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
                             encoding="utf-8")
