"""Frankfurter (ECB reference rates) and CoinGecko simple price."""
from __future__ import annotations
import json
from datetime import datetime, timezone

SERIES = [
    ("fx_usdjpy", "USD/JPY (ECB ref.)", "JPY", 5, 2, "Frankfurter/ECB"),
    ("fx_usdcny", "USD/CNY (ECB ref.)", "CNY", 5, 3, "Frankfurter/ECB"),
    ("fx_usdcad", "USD/CAD (ECB ref.)", "CAD", 5, 4, "Frankfurter/ECB"),
    ("fx_eurusd", "EUR/USD (ECB ref.)", "USD", 5, 4, "Frankfurter/ECB"),
    ("cg_btc", "Bitcoin (CoinGecko)", "USD", 2, 0, "CoinGecko"),
]
FX_URL = "https://api.frankfurter.app/{start}..?from=USD&to=JPY,CNY,CAD,EUR"
CG_URL = ("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd"
          "&include_24hr_change=true&include_last_updated_at=true")


def parse_fx(raw: bytes):
    d = json.loads(raw)
    out = {"fx_usdjpy": [], "fx_usdcny": [], "fx_usdcad": [], "fx_eurusd": []}
    for day, rates in sorted(d.get("rates", {}).items()):
        if "JPY" in rates:
            out["fx_usdjpy"].append((day, rates["JPY"]))
        if "CNY" in rates:
            out["fx_usdcny"].append((day, rates["CNY"]))
        if "CAD" in rates:
            out["fx_usdcad"].append((day, rates["CAD"]))
        if "EUR" in rates and rates["EUR"]:
            out["fx_eurusd"].append((day, round(1.0 / rates["EUR"], 5)))
    return out


def parse_latest(raw: bytes):
    """Fixture-friendly latest-only form (same shape as /latest)."""
    d = json.loads(raw)
    day = d["date"]
    r = d["rates"]
    return {"fx_usdjpy": [(day, r["JPY"])], "fx_usdcny": [(day, r["CNY"])],
            "fx_usdcad": [(day, r["CAD"])], "fx_eurusd": [(day, round(1.0 / r["EUR"], 5))]}


def fetch_fx(get, env=None):
    start = f"{datetime.now(timezone.utc).year - 1}-01-01"
    return parse_fx(get(FX_URL.format(start=start), timeout=60))


def parse_cg(raw: bytes):
    d = json.loads(raw)["bitcoin"]
    ts = d.get("last_updated_at")
    day = datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d") if ts else datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return {"cg_btc": [(day, float(d["usd"]))]}


def fetch_cg(get, env=None):
    return parse_cg(get(CG_URL))
