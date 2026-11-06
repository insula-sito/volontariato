"""Punteggio di affinità 0-100 basato su parole chiave (config/scoring.yaml)."""
from __future__ import annotations

import re
from functools import lru_cache

from .config import Config
from .models import Listing
from .textutil import word_pattern


@lru_cache(maxsize=4096)
def _pat(keyword: str) -> re.Pattern[str]:
    return word_pattern(keyword)


def _first_match(text: str, keywords: list[str]) -> str | None:
    for kw in keywords:
        if _pat(kw).search(text):
            return kw
    return None


def score(listing: Listing, cfg: Config) -> tuple[int, str]:
    sc = cfg.scoring
    text = f"{listing.titolo}\n{listing.tipo or ''}\n{listing.testo}"
    total = int(sc.get("base", 0))
    parts: list[str] = []

    gruppi_trovati = 0
    for g in sc.get("gruppi", {}).values():
        kw = _first_match(text, g["parole"])
        if kw:
            gruppi_trovati += 1
            total += int(g["peso"])
            parts.append(f"{g['etichetta']} ({kw})")

    for b in sc.get("bonus", {}).values():
        if _first_match(text, b["parole"]):
            total += int(b["peso"])
            parts.append(b["etichetta"])

    pen = sc.get("penalita", {})
    lingua = pen.get("lingua_obbligatoria")
    if lingua and any(re.search(rx, text, re.IGNORECASE) for rx in lingua.get("regex", [])):
        total -= int(lingua["peso"])
        parts.append(f"−{lingua['etichetta']}")
    manuale = pen.get("solo_manuale")
    if manuale and gruppi_trovati == 0 and _first_match(text, manuale["parole"]):
        total -= int(manuale["peso"])
        parts.append(f"−{manuale['etichetta']}")

    total = max(0, min(100, total))
    return total, (" · ".join(parts) if parts else "nessuna parola chiave")
