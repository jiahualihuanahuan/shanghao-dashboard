"""Cboe public files: VIX / VIX3M / SKEW daily CSVs and the delayed SPX option chain (for a GEX *estimate*)."""
from __future__ import annotations
import csv
import io
import json
import re
from datetime import datetime, timedelta, timezone

BASE = "https://cdn.cboe.com/api/global"
SERIES_VOL = [
    ("cboe_vix", "VIX (Cboe official close)", "pts", 4, 2, "Cboe"),
    ("cboe_vix3m", "VIX3M (Cboe official close)", "pts", 4, 2, "Cboe"),
    ("cboe_skew", "Cboe SKEW index", "pts", 4, 1, "Cboe"),
]
SERIES_GEX = [
    ("gex_spx_est", "SPX net gamma exposure estimate ($bn per 1% move)", "$bn", 4, 2, "Cboe delayed chain (estimate)"),
    ("spx_put_call_oi", "SPX put/call open-interest ratio (near expiries)", "x", 4, 2, "Cboe delayed chain"),
]
SERIES = SERIES_VOL + SERIES_GEX


def _parse_csv(raw: bytes, col: str, tail: int = 2600):
    rows = list(csv.DictReader(io.StringIO(raw.decode("utf-8", "replace"))))
    out = []
    for r in rows[-tail:]:
        try:
            d = datetime.strptime(r["DATE"].strip(), "%m/%d/%Y").strftime("%Y-%m-%d")
            out.append((d, float(r[col])))
        except (ValueError, KeyError):
            continue
    return out


def fetch_vol(get, env=None):
    out = {}
    out["cboe_vix"] = _parse_csv(get(f"{BASE}/us_indices/daily_prices/VIX_History.csv"), "CLOSE")
    out["cboe_vix3m"] = _parse_csv(get(f"{BASE}/us_indices/daily_prices/VIX3M_History.csv"), "CLOSE")
    out["cboe_skew"] = _parse_csv(get(f"{BASE}/us_indices/daily_prices/SKEW_History.csv"), "SKEW")
    return out


_OPT = re.compile(r"^([A-Z]+)(\d{6})([CP])(\d{8})$")


def compute_gex(payload: dict, horizon_days: int = 45, today: datetime | None = None):
    """Net dealer gamma *estimate* under the common (crude) assumption: dealers are long calls / short puts.

    GEX = sum(sign * gamma * open_interest * 100 * spot^2 * 0.01) over options expiring within `horizon_days`.
    Returns (net_gex_usd_bn, put_call_oi_ratio, as_of_date)."""
    data = payload["data"]
    spot = float(data["current_price"])
    ts = payload.get("timestamp")
    try:
        as_of = datetime.strptime(ts[:10], "%Y-%m-%d")
    except Exception:
        as_of = today or datetime.now(timezone.utc)
    limit = as_of + timedelta(days=horizon_days)
    gex = 0.0
    call_oi = put_oi = 0.0
    for o in data["options"]:
        m = _OPT.match(o.get("option", ""))
        if not m:
            continue
        try:
            exp = datetime.strptime(m.group(2), "%y%m%d")
        except ValueError:
            continue
        if exp > limit:
            continue
        oi = float(o.get("open_interest") or 0)
        g = float(o.get("gamma") or 0)
        sign = 1.0 if m.group(3) == "C" else -1.0
        gex += sign * g * oi * 100.0 * spot * spot * 0.01
        if sign > 0:
            call_oi += oi
        else:
            put_oi += oi
    pc = (put_oi / call_oi) if call_oi else None
    return gex / 1e9, pc, as_of.strftime("%Y-%m-%d")


def fetch_gex(get, env=None):
    raw = get(f"{BASE}/delayed_quotes/options/_SPX.json", timeout=90)
    payload = json.loads(raw)  # ~13 MB; only aggregates are kept
    gex, pc, d = compute_gex(payload)
    out = {"gex_spx_est": [(d, round(gex, 4))]}
    if pc is not None:
        out["spx_put_call_oi"] = [(d, round(pc, 4))]
    return out
