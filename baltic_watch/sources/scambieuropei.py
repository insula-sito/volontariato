"""Scambieuropei.info — aggregatore italiano (WordPress).

Cerca con l'API WordPress gli articoli recenti che citano i Paesi baltici.
Molti annunci sono ripresi dal Portale europeo: la deduplica li unisce
quando hanno lo stesso titolo e le stesse date.
"""
from __future__ import annotations

import re
from datetime import timedelta

from ..models import Listing
from ..textutil import detect_country, find_date_ranges, parse_age, pick_range, strip_html
from .base import Source

API = "https://www.scambieuropei.info/wp-json/wp/v2/posts"
SEARCH_TERMS = ["lettonia", "lituania", "estonia", "riga", "vilnius", "tallinn"]
RELEVANT_RE = re.compile(
    r"volontar|volunteer|\bESC\b|corpo europeo di solidariet|scambi[oi] giovanil|youth exchange|"
    r"workcamp|campo di lavoro|campi di volontariato|residenz|summer camp|campo estivo",
    re.IGNORECASE,
)


class ScambiEuropeiSource(Source):
    name = "scambieuropei"
    label = "Scambieuropei"

    def fetch(self) -> list[Listing]:
        after = (self.today - timedelta(days=270)).isoformat() + "T00:00:00"
        posts: dict[int, dict] = {}
        for term in SEARCH_TERMS:
            params = {"search": term, "per_page": 50, "after": after,
                      "_fields": "id,date,link,title,content"}
            for post in self.http.get(API, params=params).json():
                posts[post["id"]] = post
        self.raw_count = len(posts)

        out = []
        for post in posts.values():
            title = strip_html(post["title"]["rendered"])
            body = strip_html(post.get("content", {}).get("rendered"))
            if not RELEVANT_RE.search(f"{title}\n{body}"):
                continue  # stage, lavori, concorsi: non è volontariato
            country = detect_country(title, body, self.cfg.paesi)
            if not country:
                continue
            start, end = pick_range(find_date_ranges(f"{title}\n{body}", self.cfg.year), self.cfg.year)
            lo, hi = parse_age(body)
            out.append(Listing(
                id=f"{self.name}:{post['id']}",
                fonte=self.name,
                titolo=title,
                url=post["link"],
                paese=country,
                inizio=start,
                fine=end,
                testo=body,
                eta_min=lo,
                eta_max=hi,
            ))
        return out
