"""Registro delle fonti attive. Per aggiungerne una, importala e aggiungila a SOURCES."""
from .base import Source
from .eyp import EYPSource
from .ivsgb import IVSGBSource
from .liepaja2027 import Liepaja2027Source
from .lunaria import LunariaSource
from .scambieuropei import ScambiEuropeiSource

SOURCES: dict[str, type[Source]] = {
    cls.name: cls
    for cls in (EYPSource, Liepaja2027Source, ScambiEuropeiSource, LunariaSource, IVSGBSource)
}

__all__ = ["SOURCES", "Source"]
