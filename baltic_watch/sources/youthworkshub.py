"""YouthWorksHub — aggregatore di offerte ESC e scambi Erasmus+.

Pagine di categoria filtrate per paese, es.
https://youthworkshub.org/category/esc-projects?country=Latvia
I dati sono incorporati nella pagina (formato Nuxt) e si leggono senza
browser. L'API del sito (api.youthworkshub.org) è vietata da robots.txt
e NON viene usata; anche /match è vietato e non viene toccato.

La lista non ha le date dell'attività: per i nuovi annunci si legge la
pagina di dettaglio (al massimo MAX_DETAILS_PER_RUN al giorno), il cui
risultato resta in cache (data/cache/youthworkshub.json). Il dettaglio
contiene il link originale del Portale europeo, usato per la deduplica.
"""
from __future__ import annotations

import json

from ..models import Listing
from ..nuxt import extract_nuxt_data, find_dicts
from ..textutil import countries_to_iso2, parse_iso, strip_html
from .base import Source

BASE = "https://youthworkshub.org"
CATEGORIES = {"esc-projects": "Volontariato ESC", "erasmus-projects": "Erasmus+ (scambi giovanili)"}
COUNTRIES = {"LV": "Latvia", "LT": "Lithuania", "EE": "Estonia"}
MAX_DETAILS_PER_RUN = 40
LIST_KEYS = {"id", "slug", "title", "country", "categorySlug"}


def parse_list_page(html: str) -> list[dict]:
    items = {}
    for d in find_dicts(extract_nuxt_data(html), LIST_KEYS):
        if d.get("id") is not None and d.get("title"):
            items[str(d["id"])] = d
    return list(items.values())


def parse_detail_page(html: str) -> dict:
    found = find_dicts(extract_nuxt_data(html), {"activityStart", "content"})
    if not found:
        raise ValueError("dettaglio senza 'activityStart'")
    d = found[0]
    text = ""
    detail = d.get("detailJson")
    if isinstance(detail, str):
        try:
            detail = json.loads(detail)
        except ValueError:
            detail = None
    if isinstance(detail, dict) and isinstance(detail.get("sections"), dict):
        text = "\n".join(strip_html(str(v)) for v in detail["sections"].values() if v)
    if not text:
        text = strip_html(d.get("content"))
    source = d.get("sourceUrl")
    if not source and isinstance(detail, dict):
        source = (detail.get("source") or {}).get("sourceUrl")
    return {
        "inizio": (d.get("activityStart") or "")[:10] or None,
        "fine": (d.get("activityEnd") or "")[:10] or None,
        "eta_min": d.get("ageMin"),
        "eta_max": d.get("ageMax"),
        "paesi_ammessi": countries_to_iso2(d.get("applyFromCountries")),
        "fonte_originale": source,
        "testo": text[:6000],
    }


class YouthWorksHubSource(Source):
    name = "youthworkshub"
    label = "YouthWorksHub"

    def fetch(self) -> list[Listing]:
        rows: dict[str, tuple[str, str, dict]] = {}
        for cat in CATEGORIES:
            for code, cname in COUNTRIES.items():
                html = self.http.get(f"{BASE}/category/{cat}", params={"country": cname}).text
                for it in parse_list_page(html):
                    if (it.get("country") or "").strip().lower() == cname.lower():
                        rows[str(it["id"])] = (cat, code, it)
        self.raw_count = len(rows)

        self._cache = cache = self.load_cache()
        todo = sorted((i for i in rows if i not in cache), key=lambda i: -int(i) if i.isdigit() else 0)
        for item_id in todo[:MAX_DETAILS_PER_RUN]:
            try:
                cache[item_id] = parse_detail_page(self.http.get(f"{BASE}/{item_id}").text)
            except Exception as exc:
                cache[item_id] = {"errore": str(exc)[:100]}
        self.pending = max(0, len(todo) - MAX_DETAILS_PER_RUN)

        out = []
        for item_id, (cat, code, it) in rows.items():
            det = cache.get(item_id)
            if not det or det.get("errore"):
                continue            # dettaglio non ancora letto: lo valutiamo nei prossimi giorni
            alt = [det["fonte_originale"]] if det.get("fonte_originale") else []
            out.append(Listing(
                id=f"{self.name}:{item_id}",
                fonte=self.name,
                titolo=strip_html(it.get("title")),
                url=f"{BASE}/{item_id}",
                url_alternativi=alt,
                organizzazione=None,
                paese=code,
                inizio=parse_iso(det.get("inizio")),
                fine=parse_iso(det.get("fine")),
                scadenza=parse_iso(it.get("deadline")),
                paesi_ammessi=det.get("paesi_ammessi"),
                testo=det.get("testo") or strip_html(it.get("excerpt")),
                tipo=CATEGORIES[cat],
                eta_min=det.get("eta_min"),
                eta_max=det.get("eta_max"),
            ))
        return out

    def finish(self, save: bool) -> None:
        cache = getattr(self, "_cache", None)
        if cache is None:
            return
        if getattr(self, "pending", 0):
            print(f"  • YouthWorksHub: {self.pending} dettagli ancora da leggere (proseguo nei prossimi giorni)")
        if save:
            self.save_cache(cache)
