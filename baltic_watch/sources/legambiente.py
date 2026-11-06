"""Legambiente — campi di volontariato (organizzazione d'invio italiana).

Il sito non ha pagine per paese né un'API pubblica: si legge la sitemap
(https://volontariato.legambiente.it/sitemap.xml) e poi le pagine dei campi,
che contengono i dati strutturati JSON-LD (paese, date, descrizione).

Per non pesare sul sito si usa una cache (data/cache/legambiente.json):
ogni pagina viene letta una volta sola e riletta solo se la sitemap indica
che è cambiata. Al massimo MAX_PAGES_PER_RUN pagine per esecuzione: il primo
popolamento della cache richiede quindi alcuni giorni. Le pagine con nomi
baltici nell'indirizzo hanno la precedenza.
"""
from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from datetime import timedelta

from bs4 import BeautifulSoup

from ..models import Listing
from ..textutil import country_from_name, parse_iso, strip_html
from .base import Source

SITEMAP = "https://volontariato.legambiente.it/sitemap.xml"
CAMP_PREFIX = "https://volontariato.legambiente.it/campi-di-volontariato/"
MAX_PAGES_PER_RUN = 120
NS = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
HINT_RE = re.compile(r"eston|latvi|lettoni|lithuan|lituan|baltic|riga|tallin|vilni|kaun|tartu|liepaj|klaiped")
THEMES = {  # codici "Area tematica" -> parole che il punteggio riconosce
    "KIDS": "children", "FEST": "festival", "SPOR": "sports", "LANG": "language camp",
    "TEACH": "teaching", "EDU": "education", "CULT": "culture", "LEAD": "camp leader",
    "MANU": "manual work", "CONS": "construction", "RENO": "renovation", "ENVI": "environment",
}


def parse_sitemap(xml_text: str) -> dict[str, str]:
    """URL dei campi -> lastmod."""
    root = ET.fromstring(xml_text.encode("utf-8"))
    out = {}
    for url in root.iter(f"{NS}url"):
        loc = (url.findtext(f"{NS}loc") or "").strip()
        if loc.startswith(CAMP_PREFIX):
            out[loc] = (url.findtext(f"{NS}lastmod") or "").strip()
    return out


def parse_camp(html: str) -> dict:
    """Estrae i dati del campo dalla pagina (JSON-LD + etichette visibili)."""
    soup = BeautifulSoup(html, "html.parser")
    event = {}
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or "")
        except ValueError:
            continue
        for obj in data if isinstance(data, list) else [data]:
            if isinstance(obj, dict) and obj.get("@type") == "Event":
                event = obj
    address = (event.get("location") or {}).get("address") or {}
    text = strip_html(str(soup.find("main") or soup))
    age = re.search(r"Età\s*(\d{2})\s*[-–]\s*(\d{2})", text)
    code = re.search(r"Codice\s+(\S+(?:\s\S+)?)\s+Appuntati", text) or re.search(r"Codice\s+(\S+)", text)
    themes = re.search(r"Area tematica\s+([A-Z]{2,6}(?:\s*,\s*[A-Z]{2,6})*)", text)
    return {
        "titolo": (event.get("name") or (soup.h1.get_text(strip=True) if soup.h1 else "")).strip(),
        "paese_nome": address.get("addressCountry"),
        "luogo": address.get("addressLocality"),
        "inizio": (event.get("startDate") or "")[:10] or None,
        "fine": (event.get("endDate") or "")[:10] or None,
        "eta_min": int(age.group(1)) if age else None,
        "eta_max": int(age.group(2)) if age else None,
        "codice": code.group(1).strip() if code else None,
        "temi": [t.strip() for t in themes.group(1).split(",")] if themes else [],
        "descrizione": strip_html(event.get("description") or "")[:3000],
        "completo": bool(re.search(r"\b(sold out|al completo|esaurito)\b", text, re.IGNORECASE)),
    }


class LegambienteSource(Source):
    name = "legambiente"
    label = "Legambiente"

    def fetch(self) -> list[Listing]:
        sitemap = parse_sitemap(self.http.get(SITEMAP).text)
        self.raw_count = len(sitemap)
        self._cache = cache = self.load_cache()
        oldest = (self.today - timedelta(days=400)).isoformat()

        todo = [u for u, lm in sitemap.items()
                if (lm or "9999") >= oldest and cache.get(u, {}).get("lastmod") != lm]
        # prima i nomi baltici, poi le pagine modificate più di recente
        todo.sort(key=lambda u: (0 if HINT_RE.search(u) else 1, -_ts(sitemap[u])))
        for url in todo[:MAX_PAGES_PER_RUN]:
            try:
                info = parse_camp(self.http.get(url).text)
            except Exception as exc:  # una pagina rotta non blocca le altre
                cache[url] = {"lastmod": sitemap[url], "errore": str(exc)[:100]}
                continue
            paese = country_from_name(info["paese_nome"], self.cfg.paesi)
            entry = {"lastmod": sitemap[url], "paese": paese, "fine": info["fine"]}
            if paese:
                entry.update(info)   # dati completi solo per i campi baltici
            cache[url] = entry
        self.pending = max(0, len(todo) - MAX_PAGES_PER_RUN)

        out = []
        for url, e in cache.items():
            if not e.get("paese") or url not in sitemap:
                continue
            testo = "\n".join(filter(None, [
                "Workcamp",
                "Themes: " + ", ".join(THEMES.get(t, t) for t in e.get("temi", [])) if e.get("temi") else "",
                f"Location: {e.get('luogo')}" if e.get("luogo") else "",
                e.get("descrizione"),
            ]))
            out.append(Listing(
                id=f"{self.name}:{url.rsplit('/', 1)[-1]}",
                fonte=self.name,
                titolo=e.get("titolo") or url.rsplit("/", 1)[-1],
                url=url,
                organizzazione="Legambiente (invio dall'Italia)",
                paese=e["paese"],
                inizio=parse_iso(e.get("inizio")),
                fine=parse_iso(e.get("fine")),
                paesi_ammessi=["IT"],
                testo=testo,
                tipo="Workcamp",
                codice_progetto=e.get("codice"),
                eta_min=e.get("eta_min"),
                eta_max=e.get("eta_max"),
                stato="full" if e.get("completo") else None,
            ))
        return out

    def finish(self, save: bool) -> None:
        cache = getattr(self, "_cache", None)
        if cache is None:
            return
        if getattr(self, "pending", 0):
            print(f"  • Legambiente: {self.pending} pagine ancora da leggere (proseguo nei prossimi giorni)")
        if save:
            self.save_cache(cache)


def _ts(lastmod: str) -> float:
    d = parse_iso(lastmod)
    return d.toordinal() if d else 0
