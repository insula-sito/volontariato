"""Registro delle fonti attive. Per aggiungerne una, importala e aggiungila a SOURCES."""
from .base import Source
from .eyp import EYPSource
from .liepaja2027 import Liepaja2027Source
from .scambieuropei import ScambiEuropeiSource

SOURCES: dict[str, type[Source]] = {
    cls.name: cls
    for cls in (EYPSource, Liepaja2027Source, ScambiEuropeiSource)
}

__all__ = ["SOURCES", "Source"]
