"""Visas Iespējas (visasiespejas.lv) — aggregatore lettone di opportunità per giovani.

Il sito legge i dati da un'API GraphQL pubblica (https://api.visasiespejas.lv/graphql).
Il volontariato è tra gli "eventi", categorie "brivpratigi" (Voluntary work) e
"exchange-programme". Molti annunci sono locali e in lettone; il paese non è un
campo dell'API, quindi si deduce dal testo: gli annunci con un paese non baltico
nel titolo (es. "Volunteer in Slovenia") vengono scartati, gli altri si
considerano in Lettonia salvo diversa indicazione nel testo.
"""
from __future__ import annotations

from ..models import Listing
from ..textutil import (detect_country, flag_countries, mentions_foreign_country, parse_iso,
                        strip_html, to_text)
from .base import Source

API = "https://api.visasiespejas.lv/graphql"
SITE = "https://visasiespejas.lv/event/{slug}"
CATEGORIES = {"brivpratigi": "Volontariato", "exchange-programme": "Scambio / programma di mobilità"}
QUERY = """
query($f: EventWhereInput) {
  events(where: $f, take: 100, skip: 0, orderBy: [{createdAt: desc}]) {
    id name slug city placeName startTime endTime deadline createdAt online
    description participantMinAge participantMaxAge isTravelPaid language
    category { slug }
    organization { name }
  }
}
"""


class VisasIespejasSource(Source):
    name = "visasiespejas"
    label = "Visas Iespējas"

    def fetch(self) -> list[Listing]:
        body = {"query": QUERY, "variables": {"f": {"category": {"slug": {"in": list(CATEGORIES)}}}}}
        data = self.http.post(API, json=body, headers={"Origin": "https://visasiespejas.lv"}).json()
        if data.get("errors"):
            raise ValueError(f"errore GraphQL: {str(data['errors'])[:150]}")
        events = data["data"]["events"] or []
        self.raw_count = len(events)

        out = []
        for e in events:
            title = strip_html(to_text(e.get("name")))
            if e.get("online") or mentions_foreign_country(title):
                continue
            desc = strip_html(e.get("description"))
            flags = flag_countries(f"{title} {desc[:400]}")
            if flags and not flags & {"LV", "LT", "EE"}:
                continue        # es. "🇮🇹" a inizio descrizione: attività all'estero
            where = " ".join(filter(None, [to_text(e.get("city")), to_text(e.get("placeName"))]))
            paese = detect_country(f"{title} {where}", desc, self.cfg.paesi) or "LV"
            langs = [l.lower() for l in (e.get("language") or [])]
            extra = []
            if langs and "en" not in langs:
                extra.append("Lingua dell'annuncio: solo lettone (latvian only)")
            if e.get("isTravelPaid"):
                extra.append("Travel costs covered")
            out.append(Listing(
                id=f"{self.name}:{e['id']}",
                fonte=self.name,
                titolo=title,
                url=SITE.format(slug=e["slug"]),
                organizzazione=to_text((e.get("organization") or {}).get("name")) or None,
                paese=paese,
                inizio=parse_iso(e.get("startTime")),
                fine=parse_iso(e.get("endTime")),
                scadenza=parse_iso(e.get("deadline")),
                testo="\n".join([desc[:6000], *extra]),
                tipo=CATEGORIES.get((e.get("category") or {}).get("slug"), "Evento"),
                eta_min=e.get("participantMinAge"),
                eta_max=e.get("participantMaxAge"),
            ))
        return out
