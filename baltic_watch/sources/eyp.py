"""Portale europeo per i giovani — Corpo europeo di solidarietà.

Usa l'API JSON interna che alimenta la pagina di ricerca
https://youth.europa.eu/go-abroad/volunteering/opportunities_en
(non documentata: se cambia, scatta l'avviso di salute).
I campi di contatto restituiti dall'API (nomi ed email) NON vengono letti.
"""
from __future__ import annotations

import re

from ..models import Listing
from ..textutil import parse_iso, strip_html
from .base import Source

API = "https://youth.europa.eu/api/rest/eyp/v1/search_en"
DETAIL = "https://youth.europa.eu/solidarity/opportunity/{id}_en"
PAGE_SIZE = 100
MAX_PAGES = 20
FIELDS = [
    "opid", "title", "organisation_name", "town", "country", "date_start", "date_end",
    "date_application_end", "has_no_deadline", "status", "volunteer_activity_type",
    "volunteer_countries", "description", "participant_profile", "boarding_arrangements",
    "training", "is_esc_related",
]
TYPE_LABELS = {"teams": "Volunteering team (ESC)", "individual": "Volontariato individuale (ESC)"}
CODE_TEXT_RE = re.compile(r"\b(20\d\d-\d-[A-Z]{2}\d\d-ESC\d\d-[A-Z0-9-]+)\b")


class EYPSource(Source):
    name = "eyp"
    label = "Portale europeo per i giovani (ESC)"

    def _params(self, offset: int) -> list[tuple[str, str]]:
        win_start, win_end = self.cfg.window()
        params = [("type", "Opportunity"), ("size", str(PAGE_SIZE)), ("from", str(offset))]
        for i, code in enumerate(self.cfg.paesi):
            params.append((f"filters[country][{i}]", code))
        params += [
            ("filters[date_end][operator]", ">="),
            ("filters[date_end][value]", f"{win_start.isoformat()}T00:00:00"),
            ("filters[date_end][type]", "must"),
            ("filters[date_start][operator]", "<="),
            ("filters[date_start][value]", f"{win_end.isoformat()}T23:59:59"),
            ("filters[date_start][type]", "must"),
            ("sort[created]", "desc"),
        ]
        params += [(f"fields[{i}]", f) for i, f in enumerate(FIELDS)]
        return params

    def fetch(self) -> list[Listing]:
        out: list[Listing] = []
        offset = 0
        total = None
        for _ in range(MAX_PAGES):
            data = self.http.get(API, params=self._params(offset)).json()
            hits = data["hits"]["hits"]
            total = data["hits"]["total"]["value"]
            for hit in hits:
                out.append(self._to_listing(hit["_source"]))
            offset += len(hits)
            if not hits or offset >= total:
                break
        self.raw_count = total or 0
        return out

    def _to_listing(self, s: dict) -> Listing:
        opid = s.get("opid") or s.get("id")
        tipo = s.get("volunteer_activity_type")
        sections = [
            strip_html(s.get("description")),
            strip_html(s.get("participant_profile")),
            strip_html(s.get("boarding_arrangements")),
            strip_html(s.get("training")),
        ]
        text = "\n".join(x for x in sections if x)
        if s.get("is_esc_related"):
            text += "\nEuropean Solidarity Corps"
        if tipo == "teams":
            text += "\nVolunteering team"
        return Listing(
            id=f"eyp:{opid}",
            fonte=self.name,
            titolo=(s.get("title") or "").strip(),
            url=DETAIL.format(id=opid),
            organizzazione=s.get("organisation_name"),
            paese=s.get("country"),
            inizio=parse_iso(s.get("date_start")),
            fine=parse_iso(s.get("date_end")),
            scadenza=None if s.get("has_no_deadline") else parse_iso(s.get("date_application_end")),
            paesi_ammessi=[c.upper() for c in (s.get("volunteer_countries") or [])] or None,
            testo=text,
            tipo=TYPE_LABELS.get(tipo, tipo),
            stato=s.get("status"),
        )

    def enrich(self, listing: Listing) -> None:
        """Legge il codice progetto ESC dalla pagina di dettaglio (serve per la deduplica)."""
        if listing.codice_progetto:
            return
        m = CODE_TEXT_RE.search(strip_html(self.http.get(listing.url).text))
        if m:
            listing.codice_progetto = m.group(1)
