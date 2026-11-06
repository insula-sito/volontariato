"""Lunaria — campi di volontariato internazionale (organizzazione d'invio italiana).

Usa l'endpoint JSON del widget di ricerca della pagina
https://www.lunaria.org/cerca-nel-database/ (POST, nessun login).
Paesi in codice ISO3: EST, LVA, LTU. Il catalogo estivo esce di solito a marzo:
d'inverno è normale non trovare campi baltici. Per l'avviso di salute si
contano quindi tutti i campi restituiti, anche di altri paesi.
"""
from __future__ import annotations

from datetime import timedelta

from ..models import Listing
from ..textutil import normalize_space, parse_iso, strip_html
from .base import Source

ENDPOINT = "https://www.lunaria.org/wp-content/plugins/eplacement-wp-plugin/eplacement-search.php"
SEARCH_PAGE = "https://www.lunaria.org/cerca-nel-database/"
ISO3 = {"LVA": "LV", "LTU": "LT", "EST": "EE"}
TIMESPANS = ("STV", "MTV")   # 7-29 giorni, 30-89 giorni
DETAIL_FIELDS = ("description", "descr_work", "descr_accomodation", "descr_location",
                 "descr_requirements", "descr_partner", "notes")


def _int(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def row_to_listing(r: dict) -> Listing | None:
    paese = ISO3.get((r.get("countrycode") or "").upper())
    if not paese:
        return None
    works = [r.get(f"workdesc{i}") for i in (1, 2, 3)]
    work = ", ".join(w for w in works if w)
    parts = [f"Workcamp. Type of work: {work}" if work else "Workcamp",
             f"Location: {r.get('location')}" if r.get("location") else "",
             f"Language: {r.get('langname')}" if r.get("langname") else "",
             f"Quota extra: {normalize_space(str(r.get('extrafee') or ''))}" if r.get("extrafee") else "",
             strip_html(r.get("notes"))]
    code = (r.get("code") or "").strip() or None
    return Listing(
        id=f"lunaria:{r['id']}",
        fonte="lunaria",
        titolo=normalize_space(r.get("name") or code or "Campo"),
        url=f"{SEARCH_PAGE}#{code or r['id']}",
        organizzazione="Lunaria (invio dall'Italia)",
        paese=paese,
        inizio=parse_iso(r.get("start_date")),
        fine=parse_iso(r.get("end_date")),
        paesi_ammessi=["IT"],          # Lunaria è un'organizzazione d'invio italiana
        testo="\n".join(p for p in parts if p),
        tipo="Workcamp",
        codice_progetto=code,
        eta_min=_int(r.get("min_age")),
        eta_max=_int(r.get("max_age")),
    )


class LunariaSource(Source):
    name = "lunaria"
    label = "Lunaria"

    def _search(self, start, end, timespan: str) -> list[dict]:
        body = {"eps_sender": "LUNAR", "eps_start_date": start.isoformat(),
                "eps_end_date": end.isoformat(), "eps_loose_interval": "0", "eps_gender": "",
                "eps_age": "", "eps_timespan": timespan, "eps_country": "", "eps_work": ""}
        data = self.http.post(ENDPOINT, json=body).json()
        if "results" not in data:
            raise ValueError("risposta senza 'results': formato cambiato?")
        return data["results"] or []

    def fetch(self) -> list[Listing]:
        win_start, win_end = self.cfg.window()
        start, end = win_start - timedelta(days=45), win_end + timedelta(days=45)
        if not self.historical:
            start = min(start, self.today)   # include i campi attuali: utile per l'avviso di salute
        rows: dict = {}
        for ts in TIMESPANS:
            for r in self._search(start, end, ts):
                rows[r["id"]] = r
        self.raw_count = len(rows)
        return [l for l in (row_to_listing(r) for r in rows.values()) if l]

    def enrich(self, listing: Listing) -> None:
        """Aggiunge la descrizione completa del campo."""
        native_id = listing.id.split(":", 1)[1]
        data = self.http.post(ENDPOINT, json={"eps_project_id": native_id, "rd": "1"}).json()
        res = (data.get("results") or [None])[0]
        if not res:
            return
        extra = [strip_html(res.get(k)) for k in DETAIL_FIELDS if res.get(k)]
        listing.testo = "\n".join([listing.testo, *extra])
