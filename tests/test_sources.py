from datetime import date

from baltic_watch.config import load_config
from baltic_watch.dedupe import merge
from baltic_watch.filters import evaluate
from baltic_watch.scoring import score
from baltic_watch.sources.ivsgb import parse_detail, parse_list
from baltic_watch.sources.lunaria import row_to_listing

TODAY = date(2027, 3, 20)

LUNARIA_ROW = {
    "id": 123, "code": "EST 27-05", "start_date": "2027-08-02", "end_date": "2027-08-15",
    "countryname": "ESTONIA", "countrycode": "EST", "name": "Summer camp for kids in Tartu",
    "workdesc1": "Kids", "workdesc2": "Sports projects", "workdesc3": None,
    "location": "Tartu", "langname": "English", "extrafee": "0 EUR",
    "min_age": "20", "max_age": 99, "notes": "",
}

IVS_HTML = """
<div class="jet-listing-grid__items">
 <div class="jet-listing-grid__item" data-post-id="901">
  <div class="jet-listing-dynamic-field__content">Summer camp for kids in Tartu</div>
  <div class="jet-listing-dynamic-field__content">Estonia</div>
  <div class="jet-listing-dynamic-field__content">Kids, Sports</div>
  <div class="jet-listing-dynamic-field__content">02/08/2027</div>
  <div class="jet-listing-dynamic-field__content">15/08/2027</div>
  <div class="jet-listing-dynamic-field__content">10</div>
  <div class="jet-listing-dynamic-field__content">EST 27-05</div>
  <a href="https://ivsgb.org/vap-project/summer-camp-tartu/">More Details</a>
 </div>
 <div class="jet-listing-grid__item" data-post-id="902">
  <div class="jet-listing-dynamic-field__content">Forest work</div>
  <div class="jet-listing-dynamic-field__content">Iceland</div>
  <div class="jet-listing-dynamic-field__content">Environmental</div>
  <div class="jet-listing-dynamic-field__content">02/08/2027</div>
  <div class="jet-listing-dynamic-field__content">15/08/2027</div>
  <div class="jet-listing-dynamic-field__content">12</div>
  <div class="jet-listing-dynamic-field__content">SEEDS 1</div>
 </div>
</div>
"""

IVS_DETAIL = """
<html><body><nav>Kids menu</nav><main>
<h1>Summer camp for kids in Tartu</h1>
<div>Country: </div><div>Estonia</div>
<div>Start Date: </div><div>02/08/2027</div>
<div>Partner: </div><div>EstYES</div>
<div>Minimum Age: </div><div>20</div>
<div>Maximum Age:</div><div>30</div>
<div>Work Description:</div><div>Games and English lessons with children.</div>
</main><footer>© IVS</footer></body></html>
"""


def test_lunaria_riga_baltica():
    l = row_to_listing(LUNARIA_ROW)
    assert l.paese == "EE" and l.durata == 14 and l.paesi_ammessi == ["IT"]
    assert l.codice_progetto == "EST 27-05" and l.eta_min == 20
    assert row_to_listing({**LUNARIA_ROW, "countrycode": "ISL"}) is None
    cfg = load_config(2027)
    assert evaluate(l, cfg, TODAY).keep
    pts, why = score(l, cfg)
    assert "bambini" in why and "sport" in why


def test_ivsgb_tabella_e_dettaglio():
    rows = parse_list(IVS_HTML)
    assert len(rows) == 2
    assert rows[0]["country"] == "Estonia" and rows[0]["code"] == "EST 27-05"
    assert rows[0]["url"].endswith("/summer-camp-tartu/")
    assert rows[1]["url"] == "https://ivsgb.org/vap-volunteer-projects-list/"
    info = parse_detail(IVS_DETAIL)
    assert info["fields"]["minimum age"] == "20"
    assert info["fields"]["partner"] == "EstYES"
    assert "English lessons" in info["text"]
    assert "menu" not in info["text"]


def test_stesso_campo_lunaria_e_ivsgb_unito_per_codice():
    from baltic_watch.models import Listing
    lun = row_to_listing(LUNARIA_ROW)
    ivs = Listing(id="ivsgb:901", fonte="ivsgb", titolo="Summer camp (IVS)", url="https://ivsgb.org/x",
                  paese="EE", inizio=date(2027, 8, 2), fine=date(2027, 8, 15), codice_progetto="EST27-05")
    merged = merge([ivs, lun])
    assert len(merged) == 1
    assert merged[0].fonte == "lunaria" and set(merged[0].fonti) == {"lunaria", "ivsgb"}
