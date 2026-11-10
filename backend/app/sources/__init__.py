"""Per-source adapters. Every adapter is stdlib-only and takes an injectable `get(url)->bytes`."""
from . import cboe, cftc, fred, fx_crypto, nyfed, treasury, yahoo

# group -> (fetch callable, default interval minutes, series list, needs_key_env)
GROUPS = {
    "yahoo": dict(fetch=yahoo.fetch, interval=10, series=yahoo.SERIES, key=None,
                  label="Yahoo Finance (unofficial)"),
    "cboe_vol": dict(fetch=cboe.fetch_vol, interval=180, series=cboe.SERIES_VOL, key=None, label="Cboe indices (CSV)"),
    "cboe_gex": dict(fetch=cboe.fetch_gex, interval=20, series=cboe.SERIES_GEX, key=None,
                     label="Cboe delayed SPX chain (GEX estimate)"),
    "treasury_curve": dict(fetch=treasury.fetch_curve, interval=60, series=treasury.SERIES_CURVE, key=None,
                           label="US Treasury yield curve"),
    "treasury_tga": dict(fetch=treasury.fetch_tga, interval=360, series=treasury.SERIES_TGA, key=None,
                         label="US Treasury DTS (TGA)"),
    "nyfed": dict(fetch=nyfed.fetch, interval=60, series=nyfed.SERIES, key=None, label="NY Fed SOFR"),
    "cftc": dict(fetch=cftc.fetch, interval=360, series=cftc.SERIES, key=None, label="CFTC COT (weekly)"),
    "fx": dict(fetch=fx_crypto.fetch_fx, interval=360, series=[s for s in fx_crypto.SERIES if s[0].startswith("fx_")],
               key=None, label="Frankfurter / ECB FX"),
    "coingecko": dict(fetch=fx_crypto.fetch_cg, interval=10, series=[s for s in fx_crypto.SERIES if s[0] == "cg_btc"],
                      key=None, label="CoinGecko"),
    "fred": dict(fetch=fred.fetch, interval=180, series=fred.SERIES, key="FRED_API_KEY", label="FRED"),
}


def series_meta() -> dict:
    meta = {}
    for g, spec in GROUPS.items():
        for sid, label, unit, stale, dec, source in spec["series"]:
            meta[sid] = dict(id=sid, label=label, unit=unit, stale_days=stale, decimals=dec, source=source, group=g,
                             derived=False)
    for sid, label, unit, stale, dec, source in cftc.SERIES:
        meta.setdefault(sid, dict(id=sid, label=label, unit=unit, stale_days=stale, decimals=dec, source=source,
                                  group="cftc", derived=False))
    return meta
