import json
from datetime import date

from baltic_watch.config import load_config
from baltic_watch.dedupe import merge
from baltic_watch.filters import evaluate
from baltic_watch.models import Listing
from baltic_watch.nuxt import extract_nuxt_data
from baltic_watch.sources.lcc import parse_jobs, summer_section
from baltic_watch.sources.sci import SCISource
from baltic_watch.sources.visasiespejas import VisasIespejasSource
from baltic_watch.sources.youthworkshub import YouthWorksHubSource, parse_detail_page, parse_list_page
from baltic_watch.textutil import countries_to_iso2, mentions_foreign_country

TODAY = date(2027, 3, 20)
EYP_URL = "https://youth.europa.eu/solidarity/opportunity/55125_en"


def nuxt_html(arr):
    return f'<html><script type="application/json" data-nuxt-data="nuxt-app" id="__NUXT_DATA__">{json.dumps(arr)}</script></html>'


LIST_ARR = [["ShallowReactive", 1], {"data": 2}, ["ShallowReactive", 3], {"browse": 4}, [5],
            {"id": 6, "slug": 7, "title": 8, "country": 9, "categorySlug": 10, "deadline": 11, "excerpt": 12},
            31900, "31900", "🇱🇻 ESC Volunteering in Latvia — summer camp with children", "Latvia",
            "esc-projects", "2027-05-01T00:00:00", "Kids camp"]
DETAIL_ARR = [{"post": 1},
              {"activityStart": 2, "activityEnd": 3, "content": 4, "ageMin": 5, "ageMax": 6,
               "applyFromCountries": 7, "sourceUrl": 8, "detailJson": -1},
              "2027-08-01T00:00:00", "2027-08-20T00:00:00", "<p>Summer camp with children and sports</p>",
              18, 30, "Italy, Spain", EYP_URL]


class FakeHTTP:
    def __init__(self, routes):
        self.routes = routes
        self.calls = []

    def _find(self, url):
        self.calls.append(url)
        for key, val in self.routes.items():
            if key in url:
                return val
        raise AssertionError(f"URL inattesa {url}")

    def get(self, url, **kw):
        return type("R", (), {"text": self._find(url)})()

    def post(self, url, **kw):
        payload = self._find(url)
        return type("R", (), {"json": lambda self: payload})()


def test_nuxt_e_youthworkshub(tmp_path, monkeypatch):
    assert extract_nuxt_data(nuxt_html([{"a": 1}, [2], "x"])) == {"a": ["x"]}
    items = parse_list_page(nuxt_html(LIST_ARR))
    assert len(items) == 1 and items[0]["country"] == "Latvia"
    det = parse_detail_page(nuxt_html(DETAIL_ARR))
    assert det["inizio"] == "2027-08-01" and det["paesi_ammessi"] == ["IT", "ES"]
    assert det["fonte_originale"] == EYP_URL

    monkeypatch.setattr(YouthWorksHubSource, "cache_path", property(lambda self: tmp_path / "ywh.json"))
    http = FakeHTTP({"/category/": nuxt_html(LIST_ARR), "/31900": nuxt_html(DETAIL_ARR)})
    cfg = load_config(2027)
    src = YouthWorksHubSource(http, cfg, TODAY, historical=False)
    got = src.fetch()
    assert len(got) == 1 and got[0].paese == "LV" and got[0].durata == 20
    assert evaluate(got[0], cfg, TODAY).keep
    # stesso annuncio dal Portale europeo: viene unito grazie al link originale
    eyp = Listing(id="eyp:55125", fonte="eyp", titolo="Montessori", url=EYP_URL, paese="LV")
    assert len(merge([got[0], eyp])) == 1


def test_lcc():
    jobs_html = """<a href="/careers/38214/jobs/1-Faculty"><div>Faculty in International Relations</div>
                   <div>Education</div><div>Klaipėda, Lithuania</div></a>
                   <a href="/careers/38214/jobs/2-Summer-Camp-Volunteer"><div>Summer Camp Volunteer</div>
                   <div>Education</div></a>"""
    jobs = parse_jobs(jobs_html)
    assert [j["title"] for j in jobs] == ["Faculty in International Relations", "Summer Camp Volunteer"]
    assert jobs[1]["url"] == "https://lcchr.catsone.com/careers/38214/jobs/2-Summer-Camp-Volunteer"
    from baltic_watch.sources.lcc import JOB_RE
    assert not JOB_RE.search(jobs[0]["title"]) and JOB_RE.search(jobs[1]["title"])
    page = """<div><h2>Internship and volunteer opportunities</h2><p>Volunteer at kids camp</p>
              <p>Teach English to children</p><h2>Application</h2><p>Deadline</p></div>"""
    sec = summer_section(page)
    assert "Teach English" in sec and "Deadline" not in sec
    assert summer_section("<p>nothing</p>") is None


def test_sci():
    payload = {"data": {"projects": {"data": [
        {"id": "1", "title": "Kids camp", "code": "LV-1", "startDate": "2027-08-01T00:00:00+00:00",
         "endDate": "2027-08-14T00:00:00+00:00", "applicationDeadline": None, "description": "children",
         "minimumAgeOfInternationalVolunteers": 18, "maximumAgeOfInternationalVolunteers": 99,
         "freePlaces": 3, "isVolunteerUrgentlyNeeded": False, "approximateLocation": "Riga",
         "country": {"name": "Latvia"}, "projectType": {"name": "Volunteer Camp (less than 1 month)"},
         "hostOrganisation": {"name": "Host"}},
        {"id": "2", "title": "Far away", "code": "X", "startDate": None, "endDate": None,
         "country": {"name": "Nigeria"}, "projectType": {"name": "Long-term"}, "hostOrganisation": None}],
        "paging": {"currentPage": 1, "totalPages": 1, "totalCount": 2}}}}
    src = SCISource(FakeHTTP({"graphql": payload}), load_config(2027), TODAY, historical=False)
    got = src.fetch()
    assert src.raw_count == 2 and [l.id for l in got] == ["sci:1"]
    assert got[0].url == "https://www.volunteer.sci.ngo/projects/1" and got[0].durata == 14


def test_visasiespejas():
    payload = {"data": {"events": [
        {"id": "a", "name": "Youth Camp in Latvia", "slug": "youth-camp", "startTime": "2027-08-01T10:00:00Z",
         "endTime": "2027-08-12T10:00:00Z", "deadline": None, "online": False, "description": "Kids and sports",
         "language": ["en"], "isTravelPaid": True, "category": {"slug": "exchange-programme"},
         "organization": {"name": "Org"}},
        {"id": "b", "name": "Volunteer in Slovenia | Festival", "slug": "slo", "startTime": "2027-08-01T10:00:00Z",
         "endTime": "2027-08-12T10:00:00Z", "online": False, "description": "for young people from Latvia",
         "language": [], "category": {"slug": "brivpratigi"}, "organization": None},
        {"id": "c", "name": "Meklējam brīvprātīgos", "slug": "lv", "startTime": "2027-08-01T10:00:00Z",
         "endTime": "2027-08-12T10:00:00Z", "online": False, "description": "Rīgā", "language": ["lv"],
         "category": {"slug": "brivpratigi"}, "organization": None},
        {"id": "d", "name": "Jaunatnes darbinieku mobilitāte", "slug": "it", "startTime": "2027-08-01T10:00:00Z",
         "endTime": "2027-08-12T10:00:00Z", "online": False, "city": None, "placeName": None,
         "description": {"blocks": [{"key": "x", "text": "☀️🇮🇹 Ja esi vecumā no 18 gadiem"}], "entityMap": {}},
         "language": ["en"], "category": {"slug": "exchange-programme"}, "organization": {"name": "Org"}}]}}
    src = VisasIespejasSource(FakeHTTP({"graphql": payload}), load_config(2027), TODAY, historical=False)
    got = {l.id: l for l in src.fetch()}
    assert set(got) == {"visasiespejas:a", "visasiespejas:c"}     # Slovenia e Italia (🇮🇹) escluse
    assert got["visasiespejas:a"].paese == "LV"
    assert "latvian only" in got["visasiespejas:c"].testo


def test_utilita_paesi():
    assert countries_to_iso2("Austria, Italy, Spain") == ["AT", "IT", "ES"]
    assert countries_to_iso2("") is None
    assert mentions_foreign_country("Volunteer in Slovenia")
    assert not mentions_foreign_country("Youth Camp in Latvia")


def test_lcc_sezione_modificata_e_nuovo_annuncio(tmp_path):
    from baltic_watch.dedupe import keys_for
    from baltic_watch.state import State
    st = State(tmp_path / "seen.json")
    t = "LCC Klaipėda: volontariato nei campi estivi di inglese per bambini"
    old = Listing(id="lcc:summer:aaa", fonte="lcc", titolo=t, url="https://lcc.lt/summer-program#aaa",
                  paese="LT", codice_progetto="LCC-SUMMER-aaa")
    new = Listing(id="lcc:summer:bbb", fonte="lcc", titolo=t, url="https://lcc.lt/summer-program#bbb",
                  paese="LT", codice_progetto="LCC-SUMMER-bbb")
    assert st.upsert(old, keys_for(old), 55, "x", "principale", [], TODAY)
    assert st.upsert(new, keys_for(new), 55, "x", "principale", [], TODAY)   # nuovo avviso
