"""Yahoo Finance chart endpoint (UNOFFICIAL, undocumented; can change or rate-limit at any time).

One request per symbol, 1y of daily closes; the latest bar is replaced by the delayed live price."""
from __future__ import annotations
import json
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

URL = "https://query1.finance.yahoo.com/v8/finance/chart/{sym}?interval=1d&range=1y"
# series id -> (symbol, label, unit, decimals)
SYMBOLS = {
    "yh_spx": ("^GSPC", "S&P 500", "idx", 0),
    "yh_ndx": ("^NDX", "Nasdaq-100", "idx", 0),
    "yh_sox": ("^SOX", "PHLX Semiconductor (SOX)", "idx", 0),
    "yh_igv": ("IGV", "Software ETF (IGV)", "USD", 2),
    "yh_vix": ("^VIX", "VIX (live, delayed)", "pts", 2),
    "yh_vix3m": ("^VIX3M", "VIX3M (live, delayed)", "pts", 2),
    "yh_move": ("^MOVE", "ICE BofA MOVE index (rate vol)", "pts", 1),
    "yh_tnx": ("^TNX", "US 10Y yield (live, delayed)", "%", 3),
    "yh_tyx": ("^TYX", "US 30Y yield (live, delayed)", "%", 3),
    "yh_dxy": ("DX-Y.NYB", "US Dollar Index", "idx", 2),
    "yh_usdjpy": ("JPY=X", "USD/JPY (live)", "JPY", 2),
    "yh_nikkei": ("^N225", "Nikkei 225", "idx", 0),
    "yh_wti": ("CL=F", "WTI crude (front)", "USD/bbl", 2),
    "yh_brent": ("BZ=F", "Brent crude (front)", "USD/bbl", 2),
    "yh_ho": ("HO=F", "ULSD / heating oil (front)", "USD/gal", 3),
    "yh_ng": ("NG=F", "Natural gas (front)", "USD/MMBtu", 3),
    "yh_btc": ("BTC-USD", "Bitcoin (Yahoo)", "USD", 0),
    "yh_nvda": ("NVDA", "NVIDIA", "USD", 2),
    "yh_tsm": ("TSM", "TSMC (ADR)", "USD", 2),
    "yh_amd": ("AMD", "AMD", "USD", 2),
    "yh_intc": ("INTC", "Intel", "USD", 2),
    "yh_mu": ("MU", "Micron", "USD", 2),
    "yh_avgo": ("AVGO", "Broadcom", "USD", 2),
    "yh_smh": ("SMH", "Semiconductor ETF (SMH)", "USD", 2),
    "yh_crwv": ("CRWV", "CoreWeave", "USD", 2),
    "yh_msft": ("MSFT", "Microsoft", "USD", 2),
    "yh_amzn": ("AMZN", "Amazon", "USD", 2),
    "yh_googl": ("GOOGL", "Alphabet", "USD", 2),
    "yh_meta": ("META", "Meta", "USD", 2),
}
SERIES = [(sid, f"{lab} [Yahoo, unofficial]", unit, 4, dec, "Yahoo Finance (unofficial)")
          for sid, (_sym, lab, unit, dec) in SYMBOLS.items()]


def parse_chart(raw: bytes):
    """Return [(date, close)] with the latest bar overridden by regularMarketPrice."""
    res = json.loads(raw)["chart"]["result"][0]
    meta = res.get("meta", {})
    off = meta.get("gmtoffset", 0) or 0
    ts = res.get("timestamp") or []
    closes = (res.get("indicators", {}).get("quote") or [{}])[0].get("close") or []
    by_day = {}
    for t, c in zip(ts, closes):
        if c is None:
            continue
        day = datetime.fromtimestamp(t + off, timezone.utc).strftime("%Y-%m-%d")
        by_day[day] = float(c)
    px, mt = meta.get("regularMarketPrice"), meta.get("regularMarketTime")
    if px is not None and mt:
        day = datetime.fromtimestamp(mt + off, timezone.utc).strftime("%Y-%m-%d")
        by_day[day] = float(px)
    return sorted(by_day.items())


def fetch(get, env=None, pause: float | None = None, only=None):
    if pause is None:
        pause = float((env or {}).get("YAHOO_PAUSE_S", 0.35))
    out, errors = {}, []
    for sid, (sym, *_r) in SYMBOLS.items():
        if only and sid not in only:
            continue
        try:
            out[sid] = parse_chart(get(URL.format(sym=quote(sym, safe=""))))
        except Exception as e:  # keep going; partial data is still useful
            errors.append(f"{sym}: {e}")
        if pause:
            time.sleep(pause)
    if not out:
        raise RuntimeError("yahoo: no symbol fetched; " + "; ".join(errors[:3]))
    if errors:
        out["__errors__"] = errors
    return out
