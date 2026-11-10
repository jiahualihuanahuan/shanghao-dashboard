"""CFTC Traders in Financial Futures (latest weekly file). Leveraged-funds / asset-manager net positions."""
from __future__ import annotations
import csv
import io

URL = "https://www.cftc.gov/dea/newcot/FinFutWk.txt"
# contract name prefix -> series prefix
CONTRACTS = {
    "E-MINI S&P 500 -": "es",
    "NASDAQ MINI -": "nq",
    "UST 10Y NOTE -": "ty",
    "JAPANESE YEN -": "jy",
    "BITCOIN -": "btc",
}
SERIES = []
for _k, _p in CONTRACTS.items():
    SERIES.append((f"cot_{_p}_lev_net", f"COT {_p.upper()} leveraged funds net (contracts)", "ct", 12, 0, "CFTC TFF weekly"))
    SERIES.append((f"cot_{_p}_am_net", f"COT {_p.upper()} asset managers net (contracts)", "ct", 12, 0, "CFTC TFF weekly"))


def parse(text: str):
    out = {}
    for row in csv.reader(io.StringIO(text)):
        if len(row) < 17:
            continue
        name = row[0].strip()
        pref = next((p for k, p in CONTRACTS.items() if name.startswith(k)), None)
        if not pref or f"cot_{pref}_lev_net" in out:
            continue
        try:
            d = row[2].strip()
            am_l, am_s = float(row[11]), float(row[12])
            lv_l, lv_s = float(row[14]), float(row[15])
        except ValueError:
            continue
        out[f"cot_{pref}_am_net"] = [(d, am_l - am_s)]
        out[f"cot_{pref}_lev_net"] = [(d, lv_l - lv_s)]
    return out


def fetch(get, env=None):
    return parse(get(URL, timeout=60).decode("utf-8", "replace"))
