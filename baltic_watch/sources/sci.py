"""SCI — Service Civil International, database dei progetti.

Il vecchio sito workcamps.sci.ngo è protetto da Cloudflare e non viene usato.
Il nuovo database https://www.volunteer.sci.ngo/projects legge i dati da
un'API GraphQL pubblica (nessun login): si usa la stessa query della pagina,
chiedendo solo i campi utili (NON i contatti). Circa 300 progetti in tutto:
si scaricano tutti (poche richieste) e si filtra per paese.
Dall'Italia ci si candida tramite SCI Italia: l'idoneità resta da verificare.
"""
from __future__ import annotations

from ..models import Listing
from ..textutil import country_from_name, parse_iso, strip_html
from .base import Source

API = "https://63r8q.hatchboxapp.com/graphql"
SITE = "https://www.volunteer.sci.ngo/projects/{id}"
PER_PAGE = 100
MAX_PAGES = 20
QUERY = """
query ProjectList($pagination: PagingInput) {
  projects(pagination: $pagination) {
    data {
      id title code startDate endDate applicationDeadline description
      minimumAgeOfInternationalVolunteers maximumAgeOfInternationalVolunteers
      freePlaces isVolunteerUrgentlyNeeded approximateLocation
      country { name }
      projectType { name }
      hostOrganisation { name }
    }
    paging { currentPage totalPages totalCount }
  }
}
"""


class SCISource(Source):
    name = "sci"
    label = "SCI (Service Civil International)"

    def fetch(self) -> list[Listing]:
        projects: list[dict] = []
        total = 0
        for page in range(1, MAX_PAGES + 1):
            body = {"query": QUERY, "variables": {"pagination": {"pageNo": page, "perPage": PER_PAGE}}}
            data = self.http.post(API, json=body, headers={"Origin": "https://www.volunteer.sci.ngo"}).json()
            if data.get("errors"):
                raise ValueError(f"errore GraphQL: {str(data['errors'])[:150]}")
            res = data["data"]["projects"]
            projects += res["data"] or []
            total = res["paging"]["totalCount"]
            if page >= (res["paging"]["totalPages"] or 0):
                break
        self.raw_count = total

        out = []
        for p in projects:
            paese = country_from_name((p.get("country") or {}).get("name"), self.cfg.paesi)
            if not paese:
                continue
            tipo = (p.get("projectType") or {}).get("name") or "Progetto SCI"
            parts = [f"Workcamp. {tipo}", f"Location: {p.get('approximateLocation') or ''}",
                     strip_html(p.get("description"))]
            if p.get("isVolunteerUrgentlyNeeded"):
                parts.append("Urgente: cercano volontari")
            durata = None
            if not (p.get("startDate") and p.get("endDate")):
                low = tipo.lower()
                durata = 180 if "long" in low else 60 if ("medium" in low or "mid" in low) else None
            out.append(Listing(
                id=f"{self.name}:{p['id']}",
                fonte=self.name,
                titolo=(p.get("title") or p.get("code") or "Progetto SCI").strip(),
                url=SITE.format(id=p["id"]),
                organizzazione=((p.get("hostOrganisation") or {}).get("name") or "SCI") + " (via SCI)",
                paese=paese,
                inizio=parse_iso(p.get("startDate")),
                fine=parse_iso(p.get("endDate")),
                scadenza=parse_iso(p.get("applicationDeadline")),
                testo="\n".join(x for x in parts if x)[:6000],
                tipo=tipo,
                codice_progetto=(p.get("code") or "").strip() or None,
                eta_min=p.get("minimumAgeOfInternationalVolunteers"),
                eta_max=p.get("maximumAgeOfInternationalVolunteers"),
                stato="full" if p.get("freePlaces") == 0 else None,
                durata_indicata=durata,
            ))
        return out
