"""Registro delle fonti attive. Per aggiungerne una, importala e aggiungila a SOURCES."""
from .base import Source
from .estyes import EstYESSource
from .eyp import EYPSource
from .ivsgb import IVSGBSource
from .lcc import LCCSource
from .legambiente import LegambienteSource
from .liepaja2027 import Liepaja2027Source
from .lunaria import LunariaSource
from .scambieuropei import ScambiEuropeiSource
from .sci import SCISource
from .visasiespejas import VisasIespejasSource
from .youthforsmile import YouthForSmileSource
from .youthworkshub import YouthWorksHubSource

SOURCES: dict[str, type[Source]] = {
    cls.name: cls
    for cls in (EYPSource, Liepaja2027Source, ScambiEuropeiSource, LunariaSource, IVSGBSource,
                EstYESSource, YouthForSmileSource, LegambienteSource, LCCSource,
                YouthWorksHubSource, SCISource, VisasIespejasSource)
}

__all__ = ["SOURCES", "Source"]
