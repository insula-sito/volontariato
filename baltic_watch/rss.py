"""Lettore RSS minimale (senza dipendenze extra)."""
from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import date
from email.utils import parsedate_to_datetime

CONTENT_NS = "{http://purl.org/rss/1.0/modules/content/}encoded"


def parse_rss(xml_text: str) -> list[dict]:
    root = ET.fromstring(xml_text.encode("utf-8") if isinstance(xml_text, str) else xml_text)
    items = []
    for it in root.iter("item"):
        def txt(tag: str) -> str:
            el = it.find(tag)
            return (el.text or "").strip() if el is not None and el.text else ""
        published: date | None = None
        if txt("pubDate"):
            try:
                published = parsedate_to_datetime(txt("pubDate")).date()
            except (TypeError, ValueError):
                published = None
        items.append({
            "title": txt("title"),
            "link": txt("link"),
            "guid": txt("guid") or txt("link"),
            "published": published,
            "description": txt("description"),
            "content": txt(CONTENT_NS),
            "categories": [c.text.strip() for c in it.findall("category") if c.text],
        })
    return items
