"""EstYES (Estonia) — progetti pubblicati sul sito.

Feed RSS dei progetti: https://estyes.ee/en/feed/?post_type=portfolio
Il feed mescola progetti in Estonia (in inglese, per volontari stranieri) e
progetti all'estero per giovani estoni (in estone): si tengono solo i primi.
Il feed contiene solo un estratto, quindi per questi si legge la pagina.

I workcamp estivi di EstYES non sono qui: il loro database (e-vet.org/fo) è
vietato da robots.txt. Arrivano comunque tramite Lunaria e IVS GB.
"""
from __future__ import annotations

import re

from ..models import Listing
from ..rss import parse_rss
from ..textutil import (detect_country, find_date_ranges, parse_age, parse_duration_hint,
                        pick_range, strip_html)
from .base import Source

FEED = "https://estyes.ee/en/feed/?post_type=portfolio"
ENGLISH_RE = re.compile(r"\b(the|and|with|volunteers?|young people)\b", re.IGNORECASE)


def is_english(text: str) -> bool:
    return len(ENGLISH_RE.findall(text)) >= 4


class EstYESSource(Source):
    name = "estyes"
    label = "EstYES"

    def fetch(self) -> list[Listing]:
        items = parse_rss(self.http.get(FEED).text)
        self.raw_count = len(items)
        out = []
        for it in items:
            title = strip_html(it["title"])
            excerpt = strip_html(it["description"])
            if not is_english(f"{title} {excerpt}"):
                continue          # progetto all'estero per giovani estoni
            body = strip_html(self.http.get(it["link"]).text) if it["link"] else excerpt
            text = body or excerpt
            if detect_country(title, text, self.cfg.paesi) != "EE":
                continue
            start, end = pick_range(find_date_ranges(text, self.cfg.year), self.cfg.year)
            lo, hi = parse_age(text)
            m = re.search(r"[?&]p=(\d+)", it["guid"])
            out.append(Listing(
                id=f"{self.name}:{m.group(1) if m else it['link']}",
                fonte=self.name,
                titolo=title,
                url=it["link"],
                organizzazione=f"{title} (coordinato da EstYES)",
                paese="EE",
                inizio=start,
                fine=end,
                testo=text[:6000],
                tipo="Volontariato ESC (EstYES)",
                eta_min=lo,
                eta_max=hi,
                durata_indicata=None if start else parse_duration_hint(text[:3000]),
            ))
        return out
