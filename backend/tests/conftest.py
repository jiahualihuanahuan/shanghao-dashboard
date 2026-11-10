import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parent.parent
ROOT = BACKEND.parent
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(ROOT / "tools"))
FIX = Path(__file__).parent / "fixtures"


def fx(name: str) -> bytes:
    return (FIX / name).read_bytes()


def chart_json(values, symbol="X", last_price=None, gmtoffset=0, end=None):
    """Synthetic Yahoo chart payload with one daily bar per value (ending today)."""
    end = end or datetime.now(timezone.utc).replace(hour=12, minute=0, second=0, microsecond=0)
    ts = [int((end - timedelta(days=len(values) - 1 - i)).timestamp()) for i in range(len(values))]
    meta = {"symbol": symbol, "gmtoffset": gmtoffset, "regularMarketPrice": last_price if last_price is not None else values[-1],
            "regularMarketTime": ts[-1]}
    return json.dumps({"chart": {"result": [{"meta": meta, "timestamp": ts, "indicators": {"quote": [{"close": values}]}}]}}).encode()


@pytest.fixture
def fixture_get():
    """Router returning recorded fixtures for every free-data URL; yahoo symbols via `yahoo_values` dict."""
    state = {"yahoo": {}, "fail": set()}

    def get(url, headers=None, timeout=0, retries=0, backoff=0):
        from urllib.parse import unquote
        from app.http import FetchError
        for pat in state["fail"]:
            if pat in url:
                raise FetchError(f"{pat}: simulated failure")
        if "query1.finance.yahoo.com" in url:
            sym = unquote(url.split("/chart/")[1].split("?")[0])
            vals = state["yahoo"].get(sym)
            if vals is None:
                vals = [100.0 + i * 0.1 for i in range(260)]
            return chart_json(vals, sym)
        if "VIX_History" in url:
            return fx("vix_history.csv")
        if "VIX3M_History" in url:
            return fx("vix_history.csv")
        if "SKEW_History" in url:
            return fx("skew_history.csv")
        if "_SPX.json" in url:
            return fx("spx_chain_slim.json")
        if "daily_treasury_yield_curve" in url:
            return fx("treasury_curve.xml")
        if "operating_cash_balance" in url:
            return fx("tga.json")
        if "rates/secured/sofr" in url:
            return fx("sofr.json")
        if "FinFutWk" in url:
            return fx("cot_sample.txt")
        if "frankfurter" in url:
            days = {}
            for i in range(10):
                d = (datetime.now(timezone.utc) - timedelta(days=9 - i)).strftime("%Y-%m-%d")
                days[d] = {"JPY": 150.0 + i, "CNY": 6.6, "CAD": 1.4, "EUR": 0.9}
            return json.dumps({"base": "USD", "rates": days}).encode()
        if "coingecko" in url:
            return fx("coingecko.json")
        if "stlouisfed" in url:
            return json.dumps({"observations": [{"date": "2026-11-05", "value": "3.1"}, {"date": "2026-11-06", "value": "."}]}).encode()
        raise FetchError(f"unrouted url {url}")

    get.state = state
    return get
