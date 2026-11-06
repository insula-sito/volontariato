"""Filtri di idoneità: paese, date, durata, paesi ammessi, età, stato/scadenza."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from .config import Config
from .models import Listing
from .textutil import parse_age

PRINCIPALE = "principale"
BREVI = "brevi"


@dataclass
class Verdict:
    keep: bool
    sezione: str = PRINCIPALE
    avvisi: list[str] = field(default_factory=list)
    motivo_scarto: str | None = None


def _drop(reason: str) -> Verdict:
    return Verdict(keep=False, motivo_scarto=reason)


def evaluate(listing: Listing, cfg: Config, today: date, historical: bool = False) -> Verdict:
    f = cfg.filters
    avvisi: list[str] = []
    sezione = PRINCIPALE

    # Paese
    if listing.paese not in cfg.paesi:
        return _drop(f"paese non baltico ({listing.paese or 'non riconosciuto'})")

    # Stato e scadenza (ignorati nella modalità storica --year passato)
    stato = (listing.stato or "").lower()
    if stato == "draft":
        return _drop("bozza")
    if not historical:
        if stato in f.get("stati_chiusi", []):
            return _drop(f"stato: {stato}")
        if listing.scadenza and listing.scadenza < today:
            return _drop("scadenza passata")

    # Date: sovrapposizione con la finestra
    win_start, win_end = cfg.window()
    s, e = listing.inizio, listing.fine
    if s and e:
        if s > win_end or e < win_start:
            return _drop("fuori dal periodo")
    elif s or e:
        d = s or e
        if not (win_start <= d <= win_end):
            return _drop("fuori dal periodo")
        avvisi.append("date incomplete: da verificare")
    else:
        avvisi.append("date da verificare")

    # Durata
    dur = listing.durata
    du = f["durata"]
    if dur is not None:
        individuale = "individual" in (listing.tipo or "").lower()
        if dur < du["brevi_minimo"]:
            return _drop(f"troppo breve ({dur} gg)")
        if dur <= du["brevi_massimo"]:
            sezione = BREVI
        elif dur < du["minimo"]:
            return _drop(f"durata {dur} gg")
        elif dur > du["massimo"]:
            if individuale and dur <= du["individuale_massimo"]:
                avvisi.append(f"durata {dur} gg (individuale, max 2 mesi)")
            else:
                return _drop(f"troppo lungo ({dur} gg)")

    # Paesi di provenienza ammessi
    res = f["idoneita"]["paese_residenza"]
    ammessi = [c.upper() for c in (listing.paesi_ammessi or [])]
    if not ammessi:
        avvisi.append("idoneità da verificare")
    elif "ALL" not in ammessi and res not in ammessi:
        return _drop(f"{res} non tra i paesi ammessi")

    # Età
    lo, hi = listing.eta_min, listing.eta_max
    if lo is None and hi is None:
        lo, hi = parse_age(listing.testo)
    eta = f["eta"]
    if (lo is not None and lo > eta["massima"]) or (hi is not None and hi < eta["minima"]):
        return _drop(f"età {lo}-{hi}")

    return Verdict(keep=True, sezione=sezione, avvisi=avvisi)
