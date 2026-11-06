from datetime import date

from baltic_watch.config import load_config
from baltic_watch.filters import evaluate
from baltic_watch.sources import legambiente
from baltic_watch.sources.legambiente import LegambienteSource, parse_camp, parse_sitemap

SITEMAP = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
<url><loc>https://volontariato.legambiente.it/campi-di-volontariato</loc><lastmod>2027-03-01T10:00:00.000Z</lastmod></url>
<url><loc>https://volontariato.legambiente.it/campi-di-volontariato/kids-camp-tartu</loc><lastmod>2027-03-01T10:00:00.000Z</lastmod></url>
<url><loc>https://volontariato.legambiente.it/campi-di-volontariato/india-festival</loc><lastmod>2027-03-02T10:00:00.000Z</lastmod></url>
<url><loc>https://volontariato.legambiente.it/giornate-di-volontariato/spiaggia</loc><lastmod>2027-03-02T10:00:00.000Z</lastmod></url>
</urlset>"""


def camp_html(name, country, start, end):
    return f"""<html><head><script type="application/ld+json">
{{"@context":"https://schema.org","@type":"Event","name":"{name}","startDate":"{start}","endDate":"{end}",
"location":{{"@type":"Place","name":"X","address":{{"@type":"PostalAddress","addressLocality":"Tartu","addressCountry":"{country}"}}}},
"description":"Games and sports with kids."}}
</script></head><body><main><h1>{name}</h1>
<p><span>Area tematica</span> KIDS, SPOR</p><p>Età 18-30</p><p>Codice EST 27-05</p><p>Appuntati il codice del campo</p>
</main></body></html>"""


class FakeHTTP:
    def __init__(self):
        self.calls = []

    def get(self, url, **kw):
        self.calls.append(url)
        if url.endswith("sitemap.xml"):
            body = SITEMAP
        elif "tartu" in url:
            body = camp_html("Kids camp in Tartu", "ESTONIA", "2027-08-02", "2027-08-15")
        else:
            body = camp_html("Festival", "INDIA", "2027-08-02", "2027-08-15")
        return type("R", (), {"text": body})()


def test_parse_sitemap_e_camp():
    urls = parse_sitemap(SITEMAP)
    assert list(urls) == ["https://volontariato.legambiente.it/campi-di-volontariato/kids-camp-tartu",
                          "https://volontariato.legambiente.it/campi-di-volontariato/india-festival"]
    info = parse_camp(camp_html("Kids camp in Tartu", "ESTONIA", "2027-08-02", "2027-08-15"))
    assert info["paese_nome"] == "ESTONIA" and info["inizio"] == "2027-08-02"
    assert info["eta_min"] == 18 and info["codice"] == "EST 27-05" and info["temi"] == ["KIDS", "SPOR"]


def test_cache_incrementale(tmp_path, monkeypatch):
    monkeypatch.setattr(LegambienteSource, "cache_path", property(lambda self: tmp_path / "leg.json"))
    cfg = load_config(2027)
    today = date(2027, 3, 20)

    http = FakeHTTP()
    src = LegambienteSource(http, cfg, today, historical=False)
    got = src.fetch()
    src.finish(save=True)
    assert len(http.calls) == 3                 # sitemap + 2 campi; il Tartu per primo
    assert "tartu" in http.calls[1]
    assert [l.paese for l in got] == ["EE"]
    assert evaluate(got[0], cfg, today).keep
    assert "children" in got[0].testo

    http2 = FakeHTTP()
    src2 = LegambienteSource(http2, cfg, today, historical=False)
    got2 = src2.fetch()
    assert len(http2.calls) == 1                # solo la sitemap: pagine già in cache
    assert [l.titolo for l in got2] == ["Kids camp in Tartu"]


def test_limite_pagine_per_esecuzione(tmp_path, monkeypatch):
    monkeypatch.setattr(LegambienteSource, "cache_path", property(lambda self: tmp_path / "leg.json"))
    monkeypatch.setattr(legambiente, "MAX_PAGES_PER_RUN", 1)
    http = FakeHTTP()
    src = LegambienteSource(http, load_config(2027), date(2027, 3, 20), historical=False)
    src.fetch()
    assert len(http.calls) == 2 and src.pending == 1
