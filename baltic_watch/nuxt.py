"""Decodifica dei dati incorporati nelle pagine Nuxt (<script id="__NUXT_DATA__">).

Il formato è un array "appiattito" (libreria devalue): oggetti e liste
contengono indici di altri elementi dell'array; alcune liste speciali
iniziano con un'etichetta ("Reactive", "ShallowReactive", "Date", ...).
"""
from __future__ import annotations

import json
import re
import sys

_WRAPPERS = {"Reactive", "ShallowReactive", "Ref", "ShallowRef"}
_SCRIPT_RE = re.compile(r'<script[^>]*id="__NUXT_DATA__"[^>]*>(.*?)</script>', re.DOTALL)


def extract_nuxt_data(html: str):
    m = _SCRIPT_RE.search(html)
    if not m:
        raise ValueError("__NUXT_DATA__ non trovato: struttura della pagina cambiata?")
    return revive(json.loads(m.group(1)))


def revive(arr: list):
    memo: dict[int, object] = {}
    sys.setrecursionlimit(max(sys.getrecursionlimit(), 10000))

    def rv(i):
        if not isinstance(i, int) or i < 0:
            return None                      # -1 = undefined, ecc.
        if i in memo:
            return memo[i]
        v = arr[i]
        if isinstance(v, list):
            if v and isinstance(v[0], str):
                tag = v[0]
                if tag in _WRAPPERS:
                    out = rv(v[1])
                elif tag in ("EmptyRef", "EmptyShallowRef"):
                    out = None
                elif tag == "Date":
                    out = v[1]
                elif tag == "Set":
                    out = [rv(x) for x in v[1:]]
                elif tag in ("Map", "null"):
                    out = {}
                    memo[i] = out
                    for k, val in zip(v[1::2], v[2::2]):
                        out[str(rv(k))] = rv(val)
                else:
                    out = None
                memo[i] = out
                return out
            out_list: list = []
            memo[i] = out_list
            out_list.extend(rv(x) for x in v)
            return out_list
        if isinstance(v, dict):
            out_dict: dict = {}
            memo[i] = out_dict
            for k, idx in v.items():
                out_dict[k] = rv(idx)
            return out_dict
        memo[i] = v
        return v

    return rv(0)


def find_dicts(obj, required: set[str]) -> list[dict]:
    """Tutti i dizionari (annidati) che contengono le chiavi richieste."""
    found, seen, stack = [], set(), [obj]
    while stack:
        cur = stack.pop()
        if id(cur) in seen:
            continue
        seen.add(id(cur))
        if isinstance(cur, dict):
            if required <= cur.keys():
                found.append(cur)
            stack.extend(cur.values())
        elif isinstance(cur, list):
            stack.extend(cur)
    return found
