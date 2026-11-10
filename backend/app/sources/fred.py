"""FRED API (needs a free key in FRED_API_KEY; without one the group reports needs_key, never an error)."""
from __future__ import annotations
import json
from datetime import datetime, timedelta, timezone

URL = ("https://api.stlouisfed.org/fred/series/observations?series_id={sid}&api_key={key}"
       "&file_type=json&observation_start={start}")
# id -> (fred series, label, unit, stale_days, decimals)
FRED = {
    "fred_hy_oas": ("BAMLH0A0HYM2", "ICE BofA US High Yield OAS", "%", 6, 2),
    "fred_ccc_oas": ("BAMLH0A3HYC", "ICE BofA CCC & lower OAS", "%", 6, 2),
    "fred_ig_oas": ("BAMLC0A0CM", "ICE BofA US Corporate (IG) OAS", "%", 6, 2),
    "fred_t10y2y": ("T10Y2Y", "10Y minus 2Y Treasury spread", "pp", 6, 2),
    "fred_dgs10": ("DGS10", "10Y Treasury (FRED)", "%", 6, 2),
    "fred_fedfunds": ("DFF", "Effective fed funds rate", "%", 6, 2),
    "fred_walcl": ("WALCL", "Fed total assets (weekly)", "$M", 14, 0),
    "fred_rrp": ("RRPONTSYD", "Overnight reverse repo", "$bn", 6, 1),
    "fred_nfci": ("NFCI", "Chicago Fed NFCI (financial conditions)", "idx", 14, 2),
    "fred_unrate": ("UNRATE", "Unemployment rate", "%", 50, 1),
    "fred_payems": ("PAYEMS", "Nonfarm payrolls (level, thousands)", "k", 50, 0),
    "fred_ahe": ("CES0500000003", "Average hourly earnings (private)", "USD", 50, 2),
    "fred_cpi": ("CPIAUCSL", "CPI all items (index)", "idx", 50, 1),
    "fred_core_cpi": ("CPILFESL", "Core CPI (index)", "idx", 50, 1),
    "fred_brent": ("DCOILBRENTEU", "Brent spot (EIA via FRED)", "USD/bbl", 7, 2),
    "fred_jp10y": ("IRLTLT01JPM156N", "Japan 10Y govt yield (OECD, monthly)", "%", 75, 2),
    "fred_usd_broad": ("DTWEXBGS", "Broad trade-weighted USD", "idx", 7, 2),
}
SERIES = [(sid, lab, unit, st, dec, "FRED") for sid, (_f, lab, unit, st, dec) in FRED.items()]


class NeedsKey(Exception):
    pass


def parse_obs(raw: bytes):
    out = []
    for o in json.loads(raw).get("observations", []):
        try:
            out.append((o["date"], float(o["value"])))
        except (ValueError, KeyError):
            continue  # "." = missing
    return out


def fetch(get, env):
    key = (env.get("FRED_API_KEY") or "").strip()
    if not key:
        raise NeedsKey("FRED_API_KEY not set")
    start = (datetime.now(timezone.utc) - timedelta(days=800)).strftime("%Y-%m-%d")
    out, errors = {}, []
    for sid, (fid, *_r) in FRED.items():
        try:
            out[sid] = parse_obs(get(URL.format(sid=fid, key=key, start=start)))
        except Exception as e:
            errors.append(f"{fid}: {str(e).replace(key, '***')}")
    if not out:
        raise RuntimeError("fred: nothing fetched; " + "; ".join(errors[:3]))
    if errors:
        out["__errors__"] = errors
    return out
