"""Derived / "best-of" series built from base adapter series. Stdlib only.

Naming: base ids are source-prefixed (yh_, cboe_, ust_, fred_, ...). Clean ids (us10y, vix, ...) are either the
freshest of several sources or a calculation. Nothing here produces trade signals - these are indicators."""
from __future__ import annotations

Series = list  # [(date 'YYYY-MM-DD', float)] ascending


def pick(series: dict, *ids) -> Series:
    """Series (among ids) with the latest last-date; ties keep the order given."""
    best, best_d = [], ""
    for i in ids:
        s = series.get(i) or []
        if s and s[-1][0] > best_d:
            best, best_d = s, s[-1][0]
    return best


def ffill_align(a: Series, b: Series):
    """For each date in `a`, the latest `b` value at or before that date (skips dates before b starts)."""
    out, j, last = [], 0, None
    for d, v in a:
        while j < len(b) and b[j][0] <= d:
            last = b[j][1]
            j += 1
        if last is not None:
            out.append((d, v, last))
    return out


def _spread(a: Series, b: Series, f) -> Series:
    return [(d, f(x, y)) for d, x, y in ffill_align(a, b)]


def _drawdown(s: Series, n: int = 252) -> Series:
    out = []
    for i in range(len(s)):
        win = [v for _, v in s[max(0, i - n + 1): i + 1]]
        out.append((s[i][0], (s[i][1] / max(win) - 1.0) * 100.0))
    return out


# id -> (label, unit, decimals, stale_days, source, deps(list of base ids), func(series_map)->Series)
DERIVED = {
    "us10y": ("US 10Y yield (best of live/Treasury)", "%", 3, 4, "Yahoo (unofficial) / US Treasury",
              ["yh_tnx", "ust_10y"], lambda s: pick(s, "yh_tnx", "ust_10y")),
    "us30y": ("US 30Y yield (best of live/Treasury)", "%", 3, 4, "Yahoo (unofficial) / US Treasury",
              ["yh_tyx", "ust_30y"], lambda s: pick(s, "yh_tyx", "ust_30y")),
    "us2y": ("US 2Y par yield", "%", 2, 4, "US Treasury", ["ust_2y"], lambda s: s.get("ust_2y") or []),
    "curve_10y2y": ("10Y-2Y slope", "pp", 2, 4, "Yahoo / US Treasury", ["yh_tnx", "ust_10y", "ust_2y"],
                    lambda s: _spread(pick(s, "yh_tnx", "ust_10y"), s.get("ust_2y") or [], lambda x, y: x - y)),
    "curve_10y3m": ("10Y-3M slope", "pp", 2, 4, "Yahoo / US Treasury", ["yh_tnx", "ust_10y", "ust_3m"],
                    lambda s: _spread(pick(s, "yh_tnx", "ust_10y"), s.get("ust_3m") or [], lambda x, y: x - y)),
    "vix": ("VIX (best of live/Cboe)", "pts", 2, 4, "Yahoo (unofficial) / Cboe", ["yh_vix", "cboe_vix"],
            lambda s: pick(s, "yh_vix", "cboe_vix")),
    "vix3m": ("VIX3M (best of live/Cboe)", "pts", 2, 4, "Yahoo (unofficial) / Cboe", ["yh_vix3m", "cboe_vix3m"],
              lambda s: pick(s, "yh_vix3m", "cboe_vix3m")),
    "vix_term_ratio": ("VIX / VIX3M (>1 = term-structure inversion)", "x", 3, 4, "Yahoo (unofficial) / Cboe",
                       ["yh_vix", "cboe_vix", "yh_vix3m", "cboe_vix3m"],
                       lambda s: _spread(pick(s, "yh_vix", "cboe_vix"), pick(s, "yh_vix3m", "cboe_vix3m"),
                                         lambda x, y: x / y if y else float("nan"))),
    "skew": ("Cboe SKEW", "pts", 1, 4, "Cboe", ["cboe_skew"], lambda s: s.get("cboe_skew") or []),
    "move": ("MOVE index (rate-vol proxy)", "pts", 1, 4, "Yahoo (unofficial)", ["yh_move"],
             lambda s: s.get("yh_move") or []),
    "net_gex": ("SPX net gamma estimate ($bn/1%)", "$bn", 2, 4, "Cboe delayed chain (estimate)", ["gex_spx_est"],
                lambda s: s.get("gex_spx_est") or []),
    "usdjpy": ("USD/JPY (best of live/ECB)", "JPY", 2, 4, "Yahoo (unofficial) / ECB", ["yh_usdjpy", "fx_usdjpy"],
               lambda s: pick(s, "yh_usdjpy", "fx_usdjpy")),
    "btc": ("Bitcoin (best of Yahoo/CoinGecko)", "USD", 0, 3, "Yahoo (unofficial) / CoinGecko", ["yh_btc", "cg_btc"],
            lambda s: pick(s, "yh_btc", "cg_btc")),
    "brent": ("Brent (best of futures/FRED spot)", "USD/bbl", 2, 5, "Yahoo (unofficial) / FRED", ["yh_brent", "fred_brent"],
              lambda s: pick(s, "yh_brent", "fred_brent")),
    "diesel_crack": ("ULSD-Brent crack (HO*42 - Brent)", "USD/bbl", 1, 4, "Yahoo (unofficial) futures",
                     ["yh_ho", "yh_brent"],
                     lambda s: _spread(s.get("yh_ho") or [], s.get("yh_brent") or [], lambda ho, br: ho * 42.0 - br)),
    "spx": ("S&P 500", "idx", 0, 4, "Yahoo (unofficial)", ["yh_spx"], lambda s: s.get("yh_spx") or []),
    "spx_drawdown_pct": ("S&P 500 drawdown from 52w high", "%", 1, 4, "Yahoo (unofficial)", ["yh_spx"],
                         lambda s: _drawdown(s.get("yh_spx") or [])),
    "sox": ("PHLX Semiconductor index", "idx", 0, 4, "Yahoo (unofficial)", ["yh_sox"], lambda s: s.get("yh_sox") or []),
    "hy_oas": ("US HY OAS", "%", 2, 6, "FRED", ["fred_hy_oas"], lambda s: s.get("fred_hy_oas") or []),
    "ccc_oas": ("CCC & lower OAS", "%", 2, 6, "FRED", ["fred_ccc_oas"], lambda s: s.get("fred_ccc_oas") or []),
    "ig_oas": ("US IG OAS", "%", 2, 6, "FRED", ["fred_ig_oas"], lambda s: s.get("fred_ig_oas") or []),
    "sofr": ("SOFR", "%", 2, 5, "NY Fed", ["nyfed_sofr"], lambda s: s.get("nyfed_sofr") or []),
    "sofr_p99_spread": ("SOFR 99th pct - median", "pp", 2, 5, "NY Fed", ["nyfed_sofr_p99_spread"],
                        lambda s: s.get("nyfed_sofr_p99_spread") or []),
    "unrate": ("Unemployment rate", "%", 1, 50, "FRED", ["fred_unrate"], lambda s: s.get("fred_unrate") or []),
}


def deps_for(metric: str) -> list:
    if metric in DERIVED:
        return list(DERIVED[metric][5])
    return [metric]


def compute_derived(base: dict, only=None) -> dict:
    out = dict(base)
    for sid, (_l, _u, _d, _st, _src, deps, fn) in DERIVED.items():
        if only and sid not in only:
            continue
        if any(base.get(d) for d in deps):
            try:
                res = [(d, v) for d, v in fn(base) if v == v]  # drop NaN
            except Exception:
                res = []
            if res:
                out[sid] = res
    return out


def derived_meta() -> dict:
    return {sid: dict(id=sid, label=lab, unit=unit, decimals=dec, stale_days=st, source=src, group="derived",
                      derived=True, deps=deps)
            for sid, (lab, unit, dec, st, src, deps, _f) in DERIVED.items()}
