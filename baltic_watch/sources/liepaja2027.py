"""Liepāja 2027 — Capitale europea della cultura (Lettonia).

API WordPress: https://liepaja2027.lv/en/wp-json/wp/v2/
- articoli della categoria "Volunteers" (id 85, slug volunteers-en)
- articoli e pagine "participation" che parlano di volontari
"""
from __future__ import annotations

import re
from datetime import timedelta

from ..models import Listing
from ..textutil import find_date_ranges, parse_age, pick_range, strip_html
from .base import Source

API = "https://liepaja2027.lv/en/wp-json/wp/v2"
VOLUNTEERS_CATEGORY = 85
VOLUNTEER_RE = re.compile(r"volunteer|brīvprātīg|brivpratig", re.IGNORECASE)
FIELDS = "id,date,link,title,content,excerpt"


class Liepaja2027Source(Source):
    name = "liepaja2027"
    label = "Liepāja 2027"

    def fetch(self) -> list[Listing]:
        after = (self.today - timedelta(days=540)).isoformat() + "T00:00:00"
        items: dict[int, dict] = {}
        requests_ = [
            ("posts", {"categories": VOLUNTEERS_CATEGORY}),
            ("posts", {"search": "volunteer"}),
            ("participation", {"search": "volunteer"}),
        ]
        for endpoint, extra in requests_:
            params = {"per_page": 50, "after": after, "_fields": FIELDS, **extra}
            for post in self.http.get(f"{API}/{endpoint}", params=params).json():
                items[post["id"]] = post
        self.raw_count = len(items)

        out = []
        for post in items.values():
            title = strip_html(post["title"]["rendered"])
            body = strip_html(post.get("content", {}).get("rendered"))
            if not (VOLUNTEER_RE.search(title) or VOLUNTEER_RE.search(body[:1500])):
                continue
            start, end = pick_range(find_date_ranges(body, self.cfg.year), self.cfg.year)
            lo, hi = parse_age(body)
            out.append(Listing(
                id=f"{self.name}:{post['id']}",
                fonte=self.name,
                titolo=title,
                url=post["link"],
                organizzazione="Liepāja 2027",
                paese="LV",
                inizio=start,
                fine=end,
                testo=f"{body}\nEuropean Capital of Culture festival events",
                tipo="Volontariato a eventi",
                eta_min=lo,
                eta_max=hi,
            ))
        return out
