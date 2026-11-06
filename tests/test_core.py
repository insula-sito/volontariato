import json
from datetime import date
from pathlib import Path

from baltic_watch.config import load_config
from baltic_watch.dedupe import merge
from baltic_watch.filters import BREVI, evaluate
from baltic_watch.models import Listing
from baltic_watch.scoring import score
from baltic_watch.sources.eyp import EYPSource
from baltic_watch.state import State
from baltic_watch.textutil import detect_country, find_date_ranges, parse_age, pick_range

FIX = Path(__file__).parent / "fixtures"
TODAY = date(2026, 11, 6)


def eyp_53145(cfg):
    src = EYPSource(http=None, cfg=cfg, today=TODAY, historical=True)
    return src._to_listing(json.loads((FIX / "eyp_53145.json").read_text(encoding="utf-8")))


def test_53145_idoneo_e_punteggio_alto():
    cfg = load_config(2026)
    item = eyp_53145(cfg)
    assert item.paese == "LV"
    assert item.durata == 24
    assert "IT" in item.paesi_ammessi
    v = evaluate(item, cfg, TODAY, historical=True)
    assert v.keep, v.motivo_scarto
    assert v.sezione != BREVI
    pts, why = score(item, cfg)
    assert pts >= 70, why
    assert "bambini" in why and "ESC" in why


def test_53145_scartato_se_non_storico():
    cfg = load_config(2026)
    v = evaluate(eyp_53145(cfg), cfg, TODAY, historical=False)
    assert not v.keep  # chiuso e scaduto


def _listing(**kw):
    base = dict(id="x:1", fonte="x", titolo="Test", url="https://example.org", paese="LV",
                inizio=date(2027, 8, 1), fine=date(2027, 8, 20), paesi_ammessi=["IT"])
    base.update(kw)
    return Listing(**base)


def test_filtri_base():
    cfg = load_config(2027)
    assert evaluate(_listing(), cfg, TODAY).keep
    assert not evaluate(_listing(paese="PL"), cfg, TODAY).keep
    assert not evaluate(_listing(paesi_ammessi=["ES", "FR"]), cfg, TODAY).keep
    assert evaluate(_listing(paesi_ammessi=["all"]), cfg, TODAY).keep
    assert not evaluate(_listing(inizio=date(2027, 5, 1), fine=date(2027, 5, 20)), cfg, TODAY).keep
    short = evaluate(_listing(fine=date(2027, 8, 7)), cfg, TODAY)
    assert short.keep and short.sezione == BREVI
    assert not evaluate(_listing(fine=date(2027, 10, 30)), cfg, TODAY).keep
    long_ind = evaluate(_listing(tipo="Volontariato individuale (ESC)", inizio=date(2027, 7, 1),
                                 fine=date(2027, 8, 25)), cfg, TODAY)
    assert long_ind.keep
    nodates = evaluate(_listing(inizio=None, fine=None, paesi_ammessi=None), cfg, TODAY)
    assert nodates.keep and "date da verificare" in nodates.avvisi
    assert "idoneità da verificare" in nodates.avvisi
    assert not evaluate(_listing(testo="Participants aged 16-19"), cfg, TODAY).keep
    assert not evaluate(_listing(scadenza=date(2026, 10, 1)), cfg, TODAY).keep


def test_penalita_lingua():
    cfg = load_config(2027)
    a, _ = score(_listing(testo="Summer camp for children, sports and games."), cfg)
    b, why = score(_listing(testo="Summer camp for children. Knowledge of Latvian is required."), cfg)
    assert b < a and "lingua locale" in why


def test_date_parsing():
    assert pick_range(find_date_ranges("Residenza in Lettonia dal 3 al 23 agosto 2027", 2027), 2027) == \
        (date(2027, 8, 3), date(2027, 8, 23))
    assert find_date_ranges("ESC VolTeam Tallinn Estonia 13.-28.8.26", 2026)[0] == \
        (date(2026, 8, 13), date(2026, 8, 28))
    assert find_date_ranges("From 08/08/2026 to 31/08/2026", 2026)[0] == (date(2026, 8, 8), date(2026, 8, 31))
    assert find_date_ranges("28 July – 10 August 2027", 2027)[0] == (date(2027, 7, 28), date(2027, 8, 10))
    assert find_date_ranges("August 3-23, 2027", 2027)[0] == (date(2027, 8, 3), date(2027, 8, 23))


def test_eta_e_paese():
    assert parse_age("young people aged 18–30 who are open") == (18, 30)
    assert parse_age("Età 18-80") == (18, 80)
    cfg = load_config(2027)
    assert detect_country("Volontariato a Riga", "", cfg.paesi) == "LV"
    assert detect_country("ESC", "progetto a Vilnius, Lituania", cfg.paesi) == "LT"
    assert detect_country("Stage a Berlino", "", cfg.paesi) is None


def test_dedupe_per_codice_e_titolo_date():
    a = _listing(id="eyp:1", fonte="eyp", codice_progetto="2026-1-LV02-ESC51-VTJ-000402518")
    b = _listing(id="altro:9", fonte="altro", titolo="Diverso", codice_progetto="2026-1-lv02-esc51-vtj-000402518")
    c = _listing(id="terzo:5", fonte="terzo", titolo="TEST!")
    merged = merge([b, a, c])
    assert len(merged) == 1
    assert set(merged[0].fonti) == {"eyp", "altro", "terzo"}
    assert merged[0].id == "eyp:1"


def test_stato_e_salute(tmp_path):
    st = State(tmp_path / "seen.json")
    item = _listing()
    from baltic_watch.dedupe import keys_for
    assert st.upsert(item, keys_for(item), 50, "x", "principale", [], TODAY) is True
    assert st.upsert(item, keys_for(item), 50, "x", "principale", [], TODAY) is False
    assert st.record_health("eyp", False, 0, "boom", TODAY) is None
    assert st.record_health("eyp", True, 0, None, TODAY) is None
    assert "eyp" in st.record_health("eyp", True, 0, None, TODAY)
    assert st.record_health("eyp", True, 0, None, TODAY) is None   # un solo avviso
    assert "di nuovo" in st.record_health("eyp", True, 5, None, TODAY)
    st.save()
    assert State(tmp_path / "seen.json").find({"id:x:1"}) == "x:1"
