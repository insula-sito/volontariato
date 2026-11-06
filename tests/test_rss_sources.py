from datetime import date

from baltic_watch.config import load_config
from baltic_watch.rss import parse_rss
from baltic_watch.sources.estyes import is_english
from baltic_watch.sources.youthforsmile import YouthForSmileSource

FEED = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/"><channel>
<title>Test</title>
<item>
 <title>Meklējam brīvprātīgos nometnei Latvijā</title>
 <link>http://www.jaunatnesmaidam.lv/jaunumi/params/post/111/meklejam</link>
 <pubDate>Fri, 15 Jan 2027 09:35:00 +0000</pubDate>
 <description>&lt;div&gt;Starptautiska nometne Latvijā no 2. līdz 15. augustam, volunteers wanted, aged 18-30.&lt;/div&gt;</description>
</item>
<item>
 <title>Jauniešu apmaiņas projekts Francijā – meklējam dalībniekus!</title>
 <link>http://www.jaunatnesmaidam.lv/jaunumi/params/post/222/francija</link>
 <pubDate>Fri, 15 Jan 2027 09:35:00 +0000</pubDate>
 <description>Meklējam dalībniekus no Latvijā dzīvojošiem jauniešiem.</description>
</item>
<item>
 <title>Projekts veiksmīgi īstenots</title>
 <link>http://www.jaunatnesmaidam.lv/jaunumi/params/post/333/x</link>
 <pubDate>Fri, 15 Jan 2027 09:35:00 +0000</pubDate>
 <description>Paldies visiem Latvijā.</description>
</item>
</channel></rss>"""


class FakeResponse:
    def __init__(self, text):
        self.text = text


class FakeHTTP:
    def __init__(self, text):
        self.calls = []
        self._text = text

    def get(self, url, **kw):
        self.calls.append(url)
        return FakeResponse(self._text)


def test_parse_rss():
    items = parse_rss(FEED)
    assert len(items) == 3
    assert items[0]["published"] == date(2027, 1, 15)
    assert "Latvijā" in items[0]["description"]


def test_youthforsmile_tiene_solo_attivita_in_lettonia():
    cfg = load_config(2027)
    http = FakeHTTP(FEED)
    src = YouthForSmileSource(http, cfg, date(2027, 2, 1), historical=False)
    got = src.fetch()
    assert len(http.calls) == 3                      # tre feed
    assert [l.titolo for l in got] == ["Meklējam brīvprātīgos nometnei Latvijā"]
    assert got[0].paese == "LV" and got[0].url.startswith("https://")
    assert got[0].eta_min == 18
    assert src.raw_count == 3                        # stessi link nei tre feed finti


def test_estyes_lingua():
    assert is_english("Kiili Youth Centre is a youth work organisation in Estonia, providing "
                      "a safe and supportive environment for young people and volunteers")
    assert not is_english("Fotograafialaagrid Islandil (10 päeva, juuni-detsember 2026)")
