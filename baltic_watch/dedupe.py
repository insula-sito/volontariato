"""Deduplica: lo stesso progetto può comparire su più fonti.

Due annunci sono lo stesso progetto se hanno lo stesso codice progetto
(es. codice ESC) oppure lo stesso titolo normalizzato e le stesse date."""
from __future__ import annotations

import re
import unicodedata

from .models import Listing

# Ordine di preferenza: in caso di unione si tengono i dati della fonte più affidabile
SOURCE_RANK = {"eyp": 0}


def norm_title(title: str) -> str:
    t = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


def norm_code(code: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", code.upper())


def keys_for(listing: Listing) -> set[str]:
    keys = {f"id:{listing.id}"}
    if listing.codice_progetto:
        keys.add(f"code:{norm_code(listing.codice_progetto)}")
    title = norm_title(listing.titolo or "")
    if listing.inizio and listing.fine and title:
        keys.add(f"td:{title}|{listing.inizio}|{listing.fine}")
    elif len(title) >= 25:
        # senza date: stesso titolo (abbastanza lungo) = stesso annuncio
        keys.add(f"t:{title}")
    return keys


def _merge_two(a: Listing, b: Listing) -> Listing:
    # a è il "principale"; b completa i campi mancanti
    for name in ("organizzazione", "paese", "inizio", "fine", "scadenza", "paesi_ammessi",
                 "tipo", "codice_progetto", "eta_min", "eta_max", "stato"):
        if getattr(a, name) in (None, [], "") and getattr(b, name) not in (None, [], ""):
            setattr(a, name, getattr(b, name))
    if len(b.testo) > len(a.testo):
        a.testo = f"{a.testo}\n{b.testo}".strip()
    for src in b.fonti:
        if src not in a.fonti:
            a.fonti.append(src)
    for url in [b.url, *b.url_alternativi]:
        if url != a.url and url not in a.url_alternativi:
            a.url_alternativi.append(url)
    return a


def merge(listings: list[Listing]) -> list[Listing]:
    ordered = sorted(listings, key=lambda l: SOURCE_RANK.get(l.fonte, 9))
    result: list[Listing] = []
    index: dict[str, int] = {}
    for item in ordered:
        ks = keys_for(item)
        hit = next((index[k] for k in ks if k in index), None)
        if hit is None:
            result.append(item)
            pos = len(result) - 1
        else:
            result[hit] = _merge_two(result[hit], item)
            pos = hit
        for k in keys_for(result[pos]) | ks:
            index[k] = pos
    return result
