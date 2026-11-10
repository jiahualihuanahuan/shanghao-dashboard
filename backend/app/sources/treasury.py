"""US Treasury: daily par yield curve (XML feed) and Daily Treasury Statement TGA balance (FiscalData API)."""
from __future__ import annotations
import json
import re
from datetime import datetime, timezone
from urllib.parse import quote

CURVE_URL = ("https://home.treasury.gov/resource-center/data-chart-center/interest-rates/pages/xml"
             "?data=daily_treasury_yield_curve&field_tdr_date_value={key}")
TGA_URL = ("https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/dts/operating_cash_balance"
           "?sort=-record_date&page%5Bsize%5D=400&filter=account_type:eq:"
           + quote("Treasury General Account (TGA) Opening Balance"))
TENORS = {"BC_3MONTH": "ust_3m", "BC_2YEAR": "ust_2y", "BC_5YEAR": "ust_5y", "BC_10YEAR": "ust_10y",
          "BC_20YEAR": "ust_20y", "BC_30YEAR": "ust_30y"}
SERIES_CURVE = [
    ("ust_3m", "UST 3M par yield (Treasury)", "%", 4, 2, "US Treasury"),
    ("ust_2y", "UST 2Y par yield (Treasury)", "%", 4, 2, "US Treasury"),
    ("ust_5y", "UST 5Y par yield (Treasury)", "%", 4, 2, "US Treasury"),
    ("ust_10y", "UST 10Y par yield (Treasury)", "%", 4, 2, "US Treasury"),
    ("ust_20y", "UST 20Y par yield (Treasury)", "%", 4, 2, "US Treasury"),
    ("ust_30y", "UST 30Y par yield (Treasury)", "%", 4, 2, "US Treasury"),
]
SERIES_TGA = [("tga_open", "Treasury General Account opening balance", "$bn", 5, 0, "US Treasury DTS")]
SERIES = SERIES_CURVE + SERIES_TGA


def parse_curve(xml: str):
    out = {sid: [] for sid in TENORS.values()}
    for entry in re.findall(r"<m:properties>(.*?)</m:properties>", xml, flags=re.S):
        m = re.search(r"<d:NEW_DATE[^>]*>(\d{4}-\d{2}-\d{2})", entry)
        if not m:
            continue
        d = m.group(1)
        for tag, sid in TENORS.items():
            mm = re.search(rf"<d:{tag}[^>]*>([-\d.]+)</d:{tag}>", entry)
            if mm:
                out[sid].append((d, float(mm.group(1))))
    return out


def fetch_curve(get, env=None):
    now = datetime.now(timezone.utc)
    out = {sid: [] for sid in TENORS.values()}
    # current + previous year so 20/52-week lookbacks work
    for key in (str(now.year - 1), str(now.year)):
        try:
            part = parse_curve(get(CURVE_URL.format(key=key), timeout=60).decode("utf-8", "replace"))
        except Exception:
            if key == str(now.year):
                raise
            continue
        for sid, rows in part.items():
            out[sid].extend(rows)
    return {k: sorted(set(v)) for k, v in out.items()}


def parse_tga(raw: bytes):
    rows = json.loads(raw).get("data", [])
    out = []
    for r in rows:
        try:
            out.append((r["record_date"], float(r["open_today_bal"]) / 1000.0))  # $M -> $bn
        except (KeyError, ValueError, TypeError):
            continue
    return sorted(out)


def fetch_tga(get, env=None):
    return {"tga_open": parse_tga(get(TGA_URL))}
