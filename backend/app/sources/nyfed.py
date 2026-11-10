"""NY Fed markets API: SOFR with percentiles."""
from __future__ import annotations
import json

URL = "https://markets.newyorkfed.org/api/rates/secured/sofr/last/90.json"
SERIES = [
    ("nyfed_sofr", "SOFR", "%", 5, 2, "NY Fed"),
    ("nyfed_sofr_p99_spread", "SOFR 99th percentile minus median", "pp", 5, 2, "NY Fed"),
]


def parse(raw: bytes):
    rows = json.loads(raw).get("refRates", [])
    sofr, spread = [], []
    for r in rows:
        try:
            d = r["effectiveDate"]
            v = float(r["percentRate"])
            p99 = float(r["percentPercentile99"])
        except (KeyError, ValueError, TypeError):
            continue
        sofr.append((d, v))
        spread.append((d, round(p99 - v, 4)))
    return {"nyfed_sofr": sorted(sofr), "nyfed_sofr_p99_spread": sorted(spread)}


def fetch(get, env=None):
    return parse(get(URL))
