"""Youth for Smile / Jaunatne smaidam (Lettonia) — feed RSS del sito.

Feed: notizie, aggiornamenti sui campi internazionali e progetti.
Il sito è in lettone e si rivolge soprattutto a giovani lettoni che partono
per l'estero: si tengono solo gli annunci con attività in Lettonia che
cercano partecipanti. robots.txt chiede 10 secondi tra le richieste (rispettato).
I loro progetti ESC (es. "YS-2026-11-ESC") compaiono anche sul Portale europeo.
"""
from __future__ import annotations

import re
from datetime import timedelta

from ..models import Listing
from ..rss import parse_rss
from ..textutil import (find_date_ranges, parse_age, parse_duration_hint, pick_range,
                        strip_html, word_pattern)
from .base import Source

BASE = "https://www.jaunatnesmaidam.lv"
FEEDS = ["/jaunumi/rss/", "/pakalpojumi/starptautiskas-nometnes/nometnu-aktualitates/rss/",
         "/projekti/rss/"]
# "cerchiamo partecipanti/volontari" in lettone e inglese
CALL_RE = re.compile(
    r"meklējam|aicinām|pieteik|dalībniek|brīvprātīg|volunteers? wanted|looking for|call for|"
    r"\bapply\b|\bESC\b|solidaritātes korpus",
    re.IGNORECASE,
)
# attività in Lettonia: "Latvijā" (in Lettonia), "in Latvia" o una città lettone
IN_LATVIA = ["latvijā", "in latvia", "latvia"]
# paesi esteri al locativo lettone ("in Francia" = "Francijā"): se il titolo ne
# cita uno, l'attività è all'estero
FOREIGN_RE = re.compile(
    r"\b(francijā|itālijā|spānijā|vācijā|portugālē|polijā|lietuvā|igaunijā|grieķijā|turcijā|"
    r"horvātijā|rumānijā|bulgārijā|slovākijā|slovēnijā|čehijā|ungārijā|austrijā|beļģijā|"
    r"nīderlandē|somijā|zviedrijā|norvēģijā|dānijā|īrijā|islandē|gruzijā|armēnijā|ukrainā|"
    r"kiprā|maltā|sicīlijā|serbijā|maķedonijā|albānijā|moldovā|honkongā|korejā|japānā|"
    r"indijā|meksikā|kenijā|ganā|nepālā|taivānā|vjetnamā|eiropā|ārzemēs)\b",
    re.IGNORECASE,
)


class YouthForSmileSource(Source):
    name = "youthforsmile"
    label = "Youth for Smile (Jaunatne smaidam)"

    def fetch(self) -> list[Listing]:
        items: dict[str, dict] = {}
        for path in FEEDS:
            for it in parse_rss(self.http.get(BASE + path).text):
                items[it["link"]] = it
        self.raw_count = len(items)
        limit = self.today - timedelta(days=270)
        cities = self.cfg.paesi["LV"].get("citta", [])
        out = []
        for it in items.values():
            if it["published"] and it["published"] < limit:
                continue
            title = strip_html(it["title"])
            text = strip_html(it["description"])
            if not CALL_RE.search(f"{title} {text}"):
                continue
            where = f"{title}\n{text[:1500]}"
            in_lv = any(word_pattern(w).search(where) for w in IN_LATVIA + cities)
            if not in_lv or FOREIGN_RE.search(title):
                continue
            start, end = pick_range(find_date_ranges(text, self.cfg.year), self.cfg.year)
            lo, hi = parse_age(text)
            m = re.search(r"/post/(\d+)", it["link"])
            out.append(Listing(
                id=f"{self.name}:{m.group(1) if m else it['link']}",
                fonte=self.name,
                titolo=title,
                url=it["link"].replace("http://", "https://", 1),
                organizzazione="Jaunatne smaidam (Youth for Smile)",
                paese="LV",
                inizio=start,
                fine=end,
                testo=text,
                eta_min=lo,
                eta_max=hi,
                durata_indicata=None if start else parse_duration_hint(text[:2000]),
            ))
        return out
