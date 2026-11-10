"""Dashboard layout: tabs -> sections -> charts. `series` ids are base or derived ids (see derived.py).
transform: None | "yoy" (12-obs % change) | "diff12" (12-obs absolute change) | "mom" (1-obs diff) | "rebase" (=100 at start)"""

def C(id, title, series, unit="", transform=None, indicator=None, note=None, days=365, kind="line"):
    return dict(id=id, title=title, series=series if isinstance(series, list) else [series], unit=unit,
                transform=transform, indicator=indicator, note=note, days=days, kind=kind)


PANELS = [
    dict(id="rates", title="Liquidity & rates", topic="T1", charts=[
        C("us10y", "US 10Y yield", ["us10y"], "%", indicator="rates_10y",
          note="Live (delayed) with Treasury par yield fallback. His discussed level: 5.5%."),
        C("us30y", "US 30Y yield", ["us30y"], "%", indicator="rates_10y"),
        C("curve", "10Y-2Y slope", ["curve_10y2y"], "pp", indicator="curve"),
        C("move", "MOVE index (rate-vol proxy)", ["move"], "pts", indicator="rate_vol",
          note="Closest free proxy for the 6m10y swap vol he watches; not the same thing."),
        C("sofr", "SOFR and 99th-percentile spread", ["sofr"], "%", indicator="funding"),
        C("sofr_sp", "SOFR p99 minus median", ["sofr_p99_spread"], "pp", indicator="funding"),
        C("tga", "Treasury General Account (opening)", ["tga_open"], "$bn", indicator="funding"),
        C("walcl", "Fed total assets (needs FRED key)", ["fred_walcl"], "$M", indicator="funding"),
        C("rrp", "Overnight reverse repo (needs FRED key)", ["fred_rrp"], "$bn", indicator="funding"),
        C("nfci", "Chicago Fed NFCI (needs FRED key)", ["fred_nfci"], "idx", indicator="funding"),
    ]),
    dict(id="credit", title="Credit & funding", topic="T2", charts=[
        C("hy", "US high-yield OAS (needs FRED key)", ["hy_oas"], "%", indicator="credit_spreads"),
        C("ccc", "CCC & lower OAS (needs FRED key)", ["ccc_oas"], "%", indicator="credit_spreads",
          note="He says the riskiest credit reacts first."),
        C("ig", "US IG OAS (needs FRED key)", ["ig_oas"], "%", indicator="credit_spreads"),
        C("dxy", "US Dollar Index", ["yh_dxy"], "idx", indicator="japan_fx"),
        C("ai_debt", "AI-credit watch: CoreWeave and Oracle-like names", ["yh_crwv"], "USD", indicator="funding_ai_debt",
          note="CDS spreads are paid data; the equity is only a proxy."),
    ]),
    dict(id="fed", title="Fed & labor", topic="T3", charts=[
        C("ff", "Effective fed funds (needs FRED key)", ["fred_fedfunds"], "%", indicator="fed_policy", days=1000),
        C("unrate", "Unemployment rate (needs FRED key)", ["unrate"], "%", indicator="labor_inflation", days=1000),
        C("nfp", "Nonfarm payrolls, monthly change (needs FRED key)", ["fred_payems"], "k", transform="mom",
          indicator="labor_inflation", days=1000, kind="bar"),
        C("ahe", "Avg hourly earnings, YoY % (needs FRED key)", ["fred_ahe"], "%", transform="yoy",
          indicator="labor_inflation", days=1000),
        C("cpi", "CPI, YoY % (needs FRED key)", ["fred_cpi"], "%", transform="yoy", indicator="labor_inflation", days=1000),
        C("ccpi", "Core CPI, YoY % (needs FRED key)", ["fred_core_cpi"], "%", transform="yoy", indicator="labor_inflation",
          days=1000),
    ]),
    dict(id="positioning", title="Positioning, flows & valuation", topic="T4", charts=[
        C("vix", "VIX and VIX3M", ["vix", "vix3m"], "pts", indicator="vol_gamma"),
        C("vts", "VIX / VIX3M (>1 = inverted)", ["vix_term_ratio"], "x", indicator="vol_gamma"),
        C("skew", "Cboe SKEW", ["skew"], "pts", indicator="vol_gamma"),
        C("gex", "SPX net gamma estimate ($bn per 1%)", ["net_gex"], "$bn", indicator="vol_gamma",
          note="Estimate from Cboe delayed chain assuming dealers long calls/short puts. History builds from first run."),
        C("pc", "SPX put/call OI (<=45d)", ["spx_put_call_oi"], "x", indicator="vol_gamma"),
        C("spx", "S&P 500", ["spx"], "idx", indicator="positioning"),
        C("dd", "S&P 500 drawdown from 52w high", ["spx_drawdown_pct"], "%", indicator="positioning"),
        C("es_lev", "COT: S&P 500 e-mini leveraged funds net (weekly)", ["cot_es_lev_net"], "ct", indicator="cta_flows",
          note="Weekly CFTC data is a partial proxy for the CTA/fund flows he cites in dollars (paid sources)."),
        C("es_am", "COT: S&P 500 e-mini asset managers net", ["cot_es_am_net"], "ct", indicator="cta_flows"),
        C("pe", "S&P 500 forward P/E (manual input)", ["manual_fwd_pe_sp500"], "x", indicator="valuation"),
    ]),
    dict(id="ai", title="AI & semiconductors", topic="T6", charts=[
        C("semis", "Semis basket, rebased to 100", ["yh_sox", "yh_nvda", "yh_tsm", "yh_amd", "yh_intc", "yh_mu", "yh_avgo"],
          "100=start", transform="rebase", indicator="semis_memory", days=180),
        C("csp", "Hyperscalers, rebased to 100", ["yh_msft", "yh_amzn", "yh_googl", "yh_meta", "yh_crwv"], "100=start",
          transform="rebase", indicator="ai_demand", days=180),
        C("sw", "Software ETF (IGV) vs semis ETF (SMH), rebased", ["yh_igv", "yh_smh"], "100=start", transform="rebase",
          indicator="ai_demand", days=180),
        C("capex", "Hyperscaler capex guidance (manual input)", ["manual_hyperscaler_capex_guidance"], "$bn",
          indicator="ai_demand"),
        C("aicapex", "Total AI capex estimate (manual input)", ["manual_ai_capex_total_est"], "$trn", indicator="ai_demand"),
    ]),
    dict(id="macro", title="Tariffs, energy, Japan & crypto", topic="T7", charts=[
        C("brent", "Brent", ["brent"], "USD/bbl", indicator="energy"),
        C("crack", "ULSD-Brent crack", ["diesel_crack"], "USD/bbl", indicator="energy",
          note="He treats refined-product cracks (diesel) as the inflation variable, not crude alone."),
        C("ng", "Natural gas", ["yh_ng"], "USD/MMBtu", indicator="energy"),
        C("usdjpy", "USD/JPY", ["usdjpy"], "JPY", indicator="japan_fx"),
        C("nikkei", "Nikkei 225", ["yh_nikkei"], "idx", indicator="japan_fx"),
        C("jp10", "Japan 10Y yield (needs FRED key, monthly)", ["fred_jp10y"], "%", indicator="japan_fx", days=1000),
        C("cot_jy", "COT: yen futures leveraged funds net", ["cot_jy_lev_net"], "ct", indicator="japan_fx"),
        C("btc", "Bitcoin", ["btc"], "USD", indicator="crypto"),
        C("cot_btc", "COT: CME bitcoin leveraged funds net", ["cot_btc_lev_net"], "ct", indicator="crypto"),
        C("cny", "USD/CNY and USD/CAD (ECB ref.)", ["fx_usdcny"], "CNY", indicator="tariffs",
          note="No data source for tariff policy itself - see the notes feed and Shanghao view for his tariff commentary."),
    ]),
]


def all_chart_series() -> set:
    return {s for p in PANELS for c in p["charts"] for s in c["series"]}
