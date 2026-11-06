"""Interfaccia comune delle fonti.

Per aggiungere una fonte: crea un modulo in questa cartella con una classe
che eredita da Source, implementa fetch() e registrala in sources/__init__.py.
"""
from __future__ import annotations

from datetime import date

from ..config import Config
from ..http import PoliteSession
from ..models import Listing


class Source:
    #: nome breve, usato negli id, in --source e negli avvisi di salute
    name: str = "base"
    #: nome leggibile
    label: str = "Fonte"

    def __init__(self, http: PoliteSession, cfg: Config, today: date, historical: bool):
        self.http = http
        self.cfg = cfg
        self.today = today
        self.historical = historical
        #: quanti elementi la fonte ha restituito prima dei filtri: se resta 0
        #: per 3 esecuzioni di fila parte l'avviso di salute
        self.raw_count = 0

    def fetch(self) -> list[Listing]:
        """Scarica e normalizza gli annunci. Può già scartare quelli non baltici."""
        raise NotImplementedError

    def enrich(self, listing: Listing) -> None:
        """Facoltativo: completa un annuncio NUOVO che ha passato i filtri
        (es. leggendo la pagina di dettaglio). Chiamato solo quando serve."""
        return None
