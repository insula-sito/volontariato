"""Modello comune degli annunci restituiti da tutte le fonti."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass
class Listing:
    id: str                                   # "<fonte>:<id nativo>", stabile nel tempo
    fonte: str                                # nome della fonte (es. "eyp")
    titolo: str
    url: str
    organizzazione: str | None = None
    paese: str | None = None                  # codice ISO2: LV, LT, EE
    inizio: date | None = None
    fine: date | None = None
    scadenza: date | None = None
    paesi_ammessi: list[str] | None = None    # ISO2; None = non indicato; ["all"] = tutti
    testo: str = ""
    tipo: str | None = None                   # es. "Volunteering team", "Workcamp"
    codice_progetto: str | None = None        # es. codice ESC 2026-1-LV02-ESC51-VTJ-...
    eta_min: int | None = None
    eta_max: int | None = None
    stato: str | None = None                  # open / closed / full / ... se la fonte lo indica
    fonti: list[str] = field(default_factory=list)
    url_alternativi: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.fonti:
            self.fonti = [self.fonte]

    @property
    def durata(self) -> int | None:
        """Durata in giorni, estremi inclusi."""
        if self.inizio and self.fine:
            return (self.fine - self.inizio).days + 1
        return None

    @property
    def date_testo(self) -> str:
        """Le date in forma leggibile, es. 08/08–31/08/2026."""
        return format_range(self.inizio, self.fine)


def fmt_date(d: date | None) -> str:
    return d.strftime("%d/%m/%Y") if d else "?"


def format_range(start: date | None, end: date | None) -> str:
    if not start and not end:
        return "date da verificare"
    if start and end and start.year == end.year:
        return f"{start:%d/%m}–{end:%d/%m/%Y}"
    return f"{fmt_date(start)}–{fmt_date(end)}"
