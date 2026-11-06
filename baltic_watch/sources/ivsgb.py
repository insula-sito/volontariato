"""IVS GB — International Voluntary Service (Regno Unito).

Una sola pagina HTML con la tabella di tutti i progetti VAP:
https://ivsgb.org/vap-volunteer-projects-list/
(colonne: nome, paese, tipo di lavoro, inizio, fine, volontari, codice).
L'API WordPress del sito non espone il paese, quindi si legge la tabella.
Per i nuovi progetti baltici si apre la pagina di dettaglio (età, descrizione).

Nota: IVS GB è un'organizzazione d'invio britannica. Dall'Italia ci si
candida di solito tramite un partner italiano (Lunaria, Legambiente, SCI Italia):
per questo l'idoneità resta "da verificare". Il codice progetto permette di
riconoscere lo stesso campo pubblicato da Lunaria.
"""
from __future__ import annotations

import re

from bs4 import BeautifulSoup

from ..models import Listing
from ..textutil import country_from_name, normalize_space, parse_dmy
from .base import Source

LIST_URL = "https://ivsgb.org/vap-volunteer-projects-list/"
FOOTER_RE = re.compile(r"©|registered charity|privacy policy|subscribe|newsletter|cookie", re.IGNORECASE)


def parse_list(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    rows = []
    for item in soup.select("div.jet-listing-grid__item"):
        vals = [normalize_space(d.get_text(" ")) for d in item.select(".jet-listing-dynamic-field__content")]
        if len(vals) < 7:
            continue
        link = item.find("a", href=re.compile(r"/vap-project/"))
        rows.append({
            "post_id": item.get("data-post-id") or vals[6],
            "name": vals[0], "country": vals[1], "work": vals[2],
            "start": vals[3], "end": vals[4], "vols": vals[5], "code": vals[6],
            # senza link: indirizzo della lista + codice, per restare univoco
            "url": link["href"] if link else f"{LIST_URL}#{vals[6] or item.get('data-post-id')}",
        })
    return rows


def parse_detail(html: str) -> dict:
    """Estrae i campi 'Etichetta:' e il testo descrittivo dalla pagina di un progetto."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "nav", "header", "footer"]):
        tag.decompose()
    lines = [normalize_space(l) for l in soup.get_text("\n").splitlines()]
    lines = [l for l in lines if l]
    fields: dict[str, str] = {}
    start = next((i for i, l in enumerate(lines) if l.rstrip(":").strip() == "Country"), None)
    if start is None:
        return {"fields": fields, "text": ""}
    body = []
    i = start
    while i < len(lines) and len(body) < 200:
        line = lines[i]
        if FOOTER_RE.search(line) and i > start + 20:
            break
        if line.endswith(":") and i + 1 < len(lines) and not lines[i + 1].endswith(":"):
            fields[line.rstrip(":").strip().lower()] = lines[i + 1]
        body.append(line)
        i += 1
    return {"fields": fields, "text": "\n".join(body)}


class IVSGBSource(Source):
    name = "ivsgb"
    label = "IVS GB"

    def fetch(self) -> list[Listing]:
        rows = parse_list(self.http.get(LIST_URL).text)
        self.raw_count = len(rows)
        out = []
        for r in rows:
            paese = country_from_name(r["country"], self.cfg.paesi)
            if not paese:
                continue
            out.append(Listing(
                id=f"ivsgb:{r['post_id']}",
                fonte=self.name,
                titolo=r["name"],
                url=r["url"],
                organizzazione="IVS GB (dall'Italia tramite partner)",
                paese=paese,
                inizio=parse_dmy(r["start"]),
                fine=parse_dmy(r["end"]),
                testo=f"Workcamp. Type of work: {r['work']}. Volunteers: {r['vols']}",
                tipo="Workcamp",
                codice_progetto=r["code"] or None,
            ))
        return out

    def enrich(self, listing: Listing) -> None:
        if listing.url.startswith(LIST_URL):
            return
        info = parse_detail(self.http.get(listing.url).text)
        f = info["fields"]
        lo = re.search(r"\d+", f.get("minimum age", ""))
        hi = re.search(r"\d+", f.get("maximum age", ""))
        listing.eta_min = int(lo.group()) if lo else listing.eta_min
        listing.eta_max = int(hi.group()) if hi else listing.eta_max
        if f.get("partner"):
            listing.organizzazione = f"{f['partner']} (via IVS GB)"
        if info["text"]:
            listing.testo = f"{listing.testo}\n{info['text']}"
