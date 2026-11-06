"""LCC International University (Klaipėda, Lituania) — volontari nei campi estivi di inglese.

Due controlli, entrambi su pagine HTML pubbliche:
1. Portale annunci (https://lcchr.catsone.com/careers/38214, il vecchio indirizzo
   careers.catsone.com non esiste più): si tengono solo gli annunci con titoli
   da volontario/campo/counselor/stage.
2. Pagina https://lcc.lt/summer-program, sezione "Internship and volunteer
   opportunities" ("Volunteer at kids camp: teach English to children"):
   quando il testo cambia, arriva un nuovo avviso. Si aggiungono le date delle
   sessioni dei day camp (lcc.lt/day-camp-...), senza anno: da verificare.
"""
from __future__ import annotations

import hashlib
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..models import Listing
from ..textutil import normalize_space, strip_html
from .base import Source

CAREERS = "https://lcchr.catsone.com/careers/38214"
SUMMER = "https://lcc.lt/summer-program"
DAY_CAMPS = ["https://lcc.lt/day-camp-2-5th-graders", "https://lcc.lt/day-camp-5-8th-graders"]
JOB_RE = re.compile(r"volunt|camp|counsel|intern|summer|youth|english teach|teaching assistant", re.IGNORECASE)
SECTION_START = "Internship and volunteer opportunities"
SECTION_END_RE = re.compile(r"\n\s*(Application|Apply now|Costs|FAQ|Contact)\b")


def parse_jobs(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    jobs = {}
    for a in soup.find_all("a", href=re.compile(r"/careers/\d+/jobs/(\d+)")):
        num = re.search(r"/jobs/(\d+)", a["href"]).group(1)
        title = normalize_space(a.get_text(" "))
        if title:
            jobs[num] = {"id": num, "title": title, "url": urljoin(CAREERS, a["href"])}
    return list(jobs.values())


def summer_section(html: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = "\n".join(normalize_space(l) for l in soup.get_text("\n").splitlines() if l.strip())
    i = text.find(SECTION_START)
    if i < 0:
        return None
    chunk = text[i:i + 2500]
    m = SECTION_END_RE.search(chunk, len(SECTION_START))
    return chunk[:m.start()].strip() if m else chunk.strip()


def camp_sessions(html: str) -> str:
    text = strip_html(html)
    found = re.findall(r"((?:June|July|August|September)\s+\d{1,2}\s*[–-]\s*(?:[A-Z][a-z]+\s+)?\d{1,2})", text)
    return ", ".join(dict.fromkeys(found))


class LCCSource(Source):
    name = "lcc"
    label = "LCC International University (Klaipėda)"

    def fetch(self) -> list[Listing]:
        out: list[Listing] = []
        jobs = parse_jobs(self.http.get(CAREERS).text)
        for j in jobs:
            if not JOB_RE.search(j["title"]):
                continue
            out.append(Listing(
                id=f"{self.name}:job:{j['id']}", fonte=self.name, titolo=f"LCC: {j['title']}",
                url=j["url"], organizzazione="LCC International University", paese="LT",
                testo=j["title"], tipo="Annuncio LCC (campi estivi / volontariato)",
            ))

        section = summer_section(self.http.get(SUMMER).text)
        sessions = []
        for url in DAY_CAMPS:
            s = camp_sessions(self.http.get(url).text)
            if s:
                sessions.append(f"{url.rsplit('/', 1)[-1]}: {s}")
        if section:
            digest = hashlib.sha1(section.encode("utf-8")).hexdigest()[:10]
            testo = section + ("\nSessioni dei day camp (anno da verificare): " + "; ".join(sessions)
                               if sessions else "")
            out.append(Listing(
                id=f"{self.name}:summer:{digest}", fonte=self.name,
                titolo="LCC Klaipėda: volontariato nei campi estivi di inglese per bambini",
                url=f"{SUMMER}#{digest}",      # cambia con il testo: ogni modifica è un nuovo avviso
                organizzazione="LCC International University", paese="LT",
                testo=testo + "\nTeach English to children at the kids summer camp.",
                tipo="Volontariato in un campo estivo di inglese",
            ))
        self.raw_count = len(jobs) + (1 if section else 0)
        return out

    def enrich(self, listing: Listing) -> None:
        if ":job:" in listing.id:
            listing.testo = f"{listing.testo}\n{strip_html(self.http.get(listing.url).text)[:5000]}"
