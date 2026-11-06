"""Liepāja 2027 — Capitale europea della cultura (Lettonia).

API WordPress: https://liepaja2027.lv/en/wp-json/wp/v2/
- articoli della categoria "Volunteers" (id 85, slug volunteers-en)
- articoli e contenuti "participation" che parlano di volontari

Tiene solo gli inviti a candidarsi (titolo con "call", "join", "apply"...),
non le notizie sulle attività già svolte. Le date negli articoli sono spesso
quelle delle candidature, non dell'attività: per questo restano "da verificare".
"""
from __future__ import annotations

import re
from datetime import timedelta

from ..models import Listing
from ..textutil import parse_age, strip_html
from .base import Source

API = "https://liepaja2027.lv/en/wp-json/wp/v2"
VOLUNTEERS_CATEGORY = 85
VOLUNTEER_RE = re.compile(r"volunteer|brīvprātīg|brivpratig", re.IGNORECASE)
CALL_RE = re.compile(
    r"\bcalls?\b|looking for|\bjoin\b|\bapply\b|applications?|opens? doors|invit|recruit|"
    r"welcome volunteers|become a volunteer|sign up|register|open call",
    re.IGNORECASE,
)
FIELDS = "id,date,link,title,content"


class Liepaja2027Source(Source):
    name = "liepaja2027"
    label = "Liepāja 2027"

    def fetch(self) -> list[Listing]:
        after = (self.today - timedelta(days=400)).isoformat() + "T00:00:00"
        items: dict[int, dict] = {}
        queries = [
            ("posts", {"categories": VOLUNTEERS_CATEGORY}),
            ("posts", {"search": "volunteer"}),
            ("participation", {"search": "volunteer"}),
        ]
        for endpoint, extra in queries:
            params = {"per_page": 50, "after": after, "_fields": FIELDS, **extra}
            for post in self.http.get(f"{API}/{endpoint}", params=params).json():
                items[post["id"]] = post
        self.raw_count = len(items)

        out = []
        for post in items.values():
            title = strip_html(post["title"]["rendered"])
            if not (VOLUNTEER_RE.search(title) and CALL_RE.search(title)):
                continue
            body = strip_html(post.get("content", {}).get("rendered"))
            lo, hi = parse_age(body)
            out.append(Listing(
                id=f"{self.name}:{post['id']}",
                fonte=self.name,
                titolo=title,
                url=post["link"],
                organizzazione="Liepāja 2027",
                paese="LV",
                testo=f"{body}\nEuropean Capital of Culture festival events",
                tipo="Volontariato a eventi",
                eta_min=lo,
                eta_max=hi,
            ))
        return out
