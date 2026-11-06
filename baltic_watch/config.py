"""Caricamento dei file di configurazione YAML."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"


@dataclass
class Config:
    filters: dict
    scoring: dict
    year: int

    @property
    def paesi(self) -> dict:
        return self.filters["paesi"]

    def window(self) -> tuple[date, date]:
        p = self.filters["periodo"]
        sm, sd = (int(x) for x in p["inizio"].split("-"))
        em, ed = (int(x) for x in p["fine"].split("-"))
        return date(self.year, sm, sd), date(self.year, em, ed)


def load_config(year: int, config_dir: Path = CONFIG_DIR) -> Config:
    with open(config_dir / "filters.yaml", encoding="utf-8") as fh:
        filters = yaml.safe_load(fh)
    with open(config_dir / "scoring.yaml", encoding="utf-8") as fh:
        scoring = yaml.safe_load(fh)
    return Config(filters=filters, scoring=scoring, year=year)
