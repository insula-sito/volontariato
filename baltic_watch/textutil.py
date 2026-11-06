"""Funzioni di supporto: pulizia del testo, riconoscimento di paesi, date ed età."""
from __future__ import annotations

import html
import re
import warnings
from datetime import date, datetime

from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)


def strip_html(value: str | None) -> str:
    if not value:
        return ""
    text = BeautifulSoup(value, "html.parser").get_text(" ")
    return normalize_space(html.unescape(text))


def normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def word_pattern(keyword: str) -> re.Pattern[str]:
    """Regex che trova la parola/frase intera, senza distinguere maiuscole."""
    return re.compile(r"(?<!\w)" + re.escape(keyword.lower()) + r"(?!\w)", re.IGNORECASE)


# --------------------------------------------------------------------------
# Paesi
# --------------------------------------------------------------------------
def detect_country(title: str, text: str, paesi_cfg: dict) -> str | None:
    """Restituisce LV/LT/EE se il titolo (o, in mancanza, il testo) cita un
    solo paese baltico, o quello citato più spesso."""
    for chunk in (title, text):
        counts: dict[str, int] = {}
        for code, info in paesi_cfg.items():
            terms = list(info.get("sinonimi", [])) + list(info.get("citta", []))
            n = sum(len(word_pattern(t).findall(chunk or "")) for t in terms)
            if n:
                counts[code] = n
        if counts:
            return max(counts, key=lambda c: counts[c])
    return None


def country_from_name(name: str | None, paesi_cfg: dict) -> str | None:
    if not name:
        return None
    low = name.strip().lower()
    for code, info in paesi_cfg.items():
        if low == code.lower() or low in [s.lower() for s in info.get("sinonimi", [])]:
            return code
    return None


# --------------------------------------------------------------------------
# Date
# --------------------------------------------------------------------------
MONTHS = {
    "january": 1, "jan": 1, "gennaio": 1, "gen": 1,
    "february": 2, "feb": 2, "febbraio": 2,
    "march": 3, "mar": 3, "marzo": 3,
    "april": 4, "apr": 4, "aprile": 4,
    "may": 5, "maggio": 5, "mag": 5,
    "june": 6, "jun": 6, "giugno": 6, "giu": 6,
    "july": 7, "jul": 7, "luglio": 7, "lug": 7,
    "august": 8, "aug": 8, "agosto": 8, "ago": 8,
    "september": 9, "sept": 9, "sep": 9, "settembre": 9, "set": 9,
    "october": 10, "oct": 10, "ottobre": 10, "ott": 10,
    "november": 11, "nov": 11, "novembre": 11,
    "december": 12, "dec": 12, "dicembre": 12, "dic": 12,
}
_MON = r"(" + "|".join(sorted(MONTHS, key=len, reverse=True)) + r")\.?"
_SEP = r"\s*(?:-|–|—|→|fino al|until|till|through|to|al|a)\s*"
_D = r"(?<![\d.])(\d{1,2})(?:st|nd|rd|th)?"
_Y = r"(?:\s*,?\s*(\d{4}))?"

_PATTERNS = [
    # 08/08/2026 - 31/08/2026
    ("num", re.compile(r"(?<![\d.])(\d{1,2})[./](\d{1,2})[./](\d{2,4})" + _SEP +
                       r"(\d{1,2})[./](\d{1,2})[./](\d{2,4})")),
    # 2026-08-08 - 2026-08-31
    ("iso", re.compile(r"(\d{4})-(\d{2})-(\d{2})" + _SEP + r"(\d{4})-(\d{2})-(\d{2})")),
    # 7.-22.5.26  /  5. -20. 6. 2026
    ("short", re.compile(r"(?<![\d.])(\d{1,2})\.?\s*[-–]\s*(\d{1,2})\.\s*(\d{1,2})\.\s*(\d{2,4})")),
    # 3 agosto 2027 - 23 agosto 2027 / 28 July – 10 August
    ("dmdm", re.compile(_D + r"\s+" + _MON + _Y + _SEP + r"(\d{1,2})(?:st|nd|rd|th)?\s+" + _MON + _Y)),
    # dal 3 al 23 agosto 2027 / 3-23 August 2027
    ("ddm", re.compile(_D + _SEP + r"(\d{1,2})(?:st|nd|rd|th)?\s+" + _MON + _Y)),
    # August 3 - 23, 2027 / August 3 to September 2, 2027
    ("mdd", re.compile(r"(?<!\w)" + _MON + r"\s+(\d{1,2})(?:st|nd|rd|th)?" + _SEP +
                       r"(?:" + _MON + r"\s+)?(\d{1,2})(?:st|nd|rd|th)?" + _Y)),
]


def _year(value: str | None, default: int) -> int:
    if not value:
        return default
    y = int(value)
    return y + 2000 if y < 100 else y


def _safe(y: int, m: int, d: int) -> date | None:
    try:
        return date(y, m, d)
    except ValueError:
        return None


def find_date_ranges(text: str, default_year: int) -> list[tuple[date, date]]:
    """Trova intervalli di date nel testo (formati IT/EN comuni)."""
    low = (text or "").lower()
    found: list[tuple[int, date, date]] = []
    for kind, pat in _PATTERNS:
        for m in pat.finditer(low):
            g = m.groups()
            s = e = None
            if kind == "num":
                s = _safe(_year(g[2], default_year), int(g[1]), int(g[0]))
                e = _safe(_year(g[5], default_year), int(g[4]), int(g[3]))
            elif kind == "iso":
                s = _safe(int(g[0]), int(g[1]), int(g[2]))
                e = _safe(int(g[3]), int(g[4]), int(g[5]))
            elif kind == "short":
                y = _year(g[3], default_year)
                s = _safe(y, int(g[2]), int(g[0]))
                e = _safe(y, int(g[2]), int(g[1]))
            elif kind == "dmdm":
                ye = _year(g[5], default_year)
                ys = _year(g[2], ye)
                s = _safe(ys, MONTHS[g[1]], int(g[0]))
                e = _safe(ye, MONTHS[g[4]], int(g[3]))
            elif kind == "ddm":
                y = _year(g[3], default_year)
                s = _safe(y, MONTHS[g[2]], int(g[0]))
                e = _safe(y, MONTHS[g[2]], int(g[1]))
            elif kind == "mdd":
                y = _year(g[4], default_year)
                m1 = MONTHS[g[0]]
                m2 = MONTHS[g[2]] if g[2] else m1
                s = _safe(y, m1, int(g[1]))
                e = _safe(y, m2, int(g[3]))
            if s and e and e < s and e.month < s.month and e.year == s.year:
                e = _safe(e.year + 1, e.month, e.day)   # es. 28 dicembre - 5 gennaio
            if s and e and s <= e and (e - s).days <= 400:
                found.append((m.start(), s, e))
    found.sort(key=lambda t: t[0])
    out: list[tuple[date, date]] = []
    for _, s, e in found:
        if (s, e) not in out:
            out.append((s, e))
    return out


def pick_range(ranges: list[tuple[date, date]], year: int) -> tuple[date | None, date | None]:
    for s, e in ranges:
        if s.year == year or e.year == year:
            return s, e
    return (ranges[0] if ranges else (None, None))


def parse_iso(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def parse_dmy(value: str | None) -> date | None:
    """Accetta 31/08/2026, 31.08.2026, 31-08-26."""
    if not value:
        return None
    m = re.search(r"(\d{1,2})[./-](\d{1,2})[./-](\d{2,4})", value)
    if not m:
        return None
    return _safe(_year(m.group(3), 2000), int(m.group(2)), int(m.group(1)))


_DURATION = re.compile(
    r"(?<![\d-])(\d{1,3})\s*(mesi|mese|months?|settimane|settimana|weeks?|giorni|days)\b",
    re.IGNORECASE,
)
_UNIT_DAYS = {"mes": 30, "mon": 30, "set": 7, "wee": 7, "gio": 1, "day": 1}


def parse_duration_hint(text: str) -> int | None:
    """Durata indicata a parole, es. "per 12 mesi" -> 360, "2 settimane" -> 14."""
    for m in _DURATION.finditer(text or ""):
        n = int(m.group(1))
        days = n * _UNIT_DAYS[m.group(2).lower()[:3]]
        if 3 <= days <= 800:
            return days
    return None


# --------------------------------------------------------------------------
# Età
# --------------------------------------------------------------------------
_AGE_PATTERNS = [
    re.compile(r"(?:aged?|ages|età|eta|age group|age limit|limiti di età)\s*:?\s*(?:between\s+|from\s+|tra\s+|dai\s+)?"
               r"(\d{2})\s*(?:-|–|to|and|e|a|ai)\s*(\d{2})", re.IGNORECASE),
    re.compile(r"(?<!\d)(\d{2})\s*(?:-|–|to|e|a|ai)\s*(\d{2})\s*(?:years|year-olds|yo|y\.o\.|anni)", re.IGNORECASE),
]
_AGE_MIN = re.compile(r"(?<![\d/.])(\d{2})\s*\+\s*(?:years|anni|y\.o\.)?|(?:over|minimum age|età minima|almeno)\s*:?\s*(\d{2})", re.IGNORECASE)


def parse_age(text: str) -> tuple[int | None, int | None]:
    for pat in _AGE_PATTERNS:
        for m in pat.finditer(text or ""):
            lo, hi = int(m.group(1)), int(m.group(2))
            if 13 <= lo <= 40 and lo <= hi <= 99:
                return lo, hi
    m = _AGE_MIN.search(text or "")
    if m:
        lo = int(m.group(1) or m.group(2))
        if 13 <= lo <= 40:
            return lo, None
    return None, None
