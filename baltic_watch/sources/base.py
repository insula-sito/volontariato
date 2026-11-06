"""Interfaccia comune delle fonti.

Per aggiungere una fonte: crea un modulo in questa cartella con una classe
che eredita da Source, implementa fetch() e registrala in sources/__init__.py.
"""
from __future__ import annotations

import json
from datetime import date

from ..config import ROOT, Config
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

    # --- cache facoltativa su disco (data/cache/<nome>.json) -------------------
    @property
    def cache_path(self):
        return ROOT / "data" / "cache" / f"{self.name}.json"

    def load_cache(self) -> dict:
        try:
            return json.loads(self.cache_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, ValueError):
            return {}

    def save_cache(self, data: dict) -> None:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_path.write_text(json.dumps(data, ensure_ascii=False, indent=0, sort_keys=True) + "\n",
                                   encoding="utf-8")

    def finish(self, save: bool) -> None:
        """Chiamato a fine esecuzione: save=False con --dry-run."""
        return None
