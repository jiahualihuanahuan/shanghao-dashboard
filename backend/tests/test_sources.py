import json

import pytest

from app.sources import cboe, cftc, fred, fx_crypto, nyfed, treasury, yahoo
from conftest import fx, chart_json


def test_cboe_csv_parse():
    rows = cboe._parse_csv(fx("vix_history.csv"), "CLOSE")
    assert len(rows) == 40 and rows[0][0] < rows[-1][0] and all(isinstance(v, float) for _, v in rows)
    assert rows[-1][0].startswith("2026")


def test_cboe_vol_group(fixture_get):
    out = cboe.fetch_vol(fixture_get)
    assert set(out) == {"cboe_vix", "cboe_vix3m", "cboe_skew"}
    assert 100 < out["cboe_skew"][-1][1] < 200


def test_gex_estimate_shape_and_sign():
    payload = json.loads(fx("spx_chain_slim.json"))
    gex, pc, d = cboe.compute_gex(payload)
    assert d == payload["timestamp"][:10]
    assert pc and pc > 0
    # sign check: only calls -> positive, only puts -> negative
    spot = 1000.0
    calls = {"timestamp": "2026-11-10 10:00:00", "data": {"current_price": spot, "options": [
        {"option": "SPX261120C01000000", "gamma": 0.001, "open_interest": 100}]}}
    puts = {"timestamp": "2026-11-10 10:00:00", "data": {"current_price": spot, "options": [
        {"option": "SPX261120P01000000", "gamma": 0.001, "open_interest": 100}]}}
    g_c, _, _ = cboe.compute_gex(calls)
    g_p, _, _ = cboe.compute_gex(puts)
    assert g_c > 0 > g_p
    assert abs(g_c - 0.001 * 100 * 100 * spot * spot * 0.01 / 1e9) < 1e-9
    far = {"timestamp": "2026-11-10 10:00:00", "data": {"current_price": spot, "options": [
        {"option": "SPX270120C01000000", "gamma": 0.001, "open_interest": 100}]}}
    assert cboe.compute_gex(far)[0] == 0   # beyond the 45-day horizon


def test_gex_group(fixture_get):
    out = cboe.fetch_gex(fixture_get)
    assert "gex_spx_est" in out and "spx_put_call_oi" in out


def test_treasury_curve_and_tga():
    c = treasury.parse_curve(fx("treasury_curve.xml").decode())
    assert c["ust_10y"] and c["ust_2y"][-1][0].startswith("2026-11")
    assert c["ust_10y"][0][1] == pytest.approx(4.91) or len(c["ust_10y"]) > 1
    t = treasury.parse_tga(fx("tga.json"))
    assert t and t == sorted(t) and 100 < t[-1][1] < 2000   # $bn


def test_nyfed_sofr():
    o = nyfed.parse(fx("sofr.json"))
    assert o["nyfed_sofr"][-1][1] == 3.88
    assert o["nyfed_sofr_p99_spread"][-1][1] == pytest.approx(0.08)


def test_cftc_net_positions():
    o = cftc.parse(fx("cot_sample.txt").decode())
    assert set(o) >= {"cot_es_lev_net", "cot_es_am_net", "cot_jy_lev_net", "cot_btc_lev_net", "cot_ty_lev_net", "cot_nq_lev_net"}
    assert o["cot_es_lev_net"][0][0] == "2026-11-03"


def test_yahoo_parse_overrides_latest_bar():
    raw = chart_json([1.0, 2.0, 3.0], last_price=3.5)
    pts = yahoo.parse_chart(raw)
    assert len(pts) == 3 and pts[-1][1] == 3.5 and pts[0][0] < pts[-1][0]
    real = yahoo.parse_chart(fx("yahoo_tnx.json"))
    assert len(real) >= 15 and 2 < real[-1][1] < 8


def test_yahoo_partial_failure_is_reported(fixture_get):
    fixture_get.state["fail"].add("%5EMOVE")
    out = yahoo.fetch(fixture_get, {}, pause=0, only={"yh_move", "yh_vix"})
    assert "yh_vix" in out and "yh_move" not in out and out["__errors__"]


def test_yahoo_all_fail_raises():
    def bad(url, **k):
        raise RuntimeError("boom")
    with pytest.raises(RuntimeError):
        yahoo.fetch(bad, {}, pause=0, only={"yh_vix"})


def test_fx_and_coingecko():
    o = fx_crypto.parse_latest(fx("frankfurter.json"))
    assert o["fx_usdjpy"][0][1] > 50
    b = fx_crypto.parse_cg(fx("coingecko.json"))
    assert b["cg_btc"][0][1] > 1000
    rng = fx_crypto.parse_fx(json.dumps({"rates": {"2026-11-09": {"JPY": 158.0, "EUR": 0.9, "CNY": 6.6, "CAD": 1.4}}}).encode())
    assert rng["fx_eurusd"][0][1] == pytest.approx(1.11111, abs=1e-4)


def test_fred_needs_key_and_key_redaction():
    with pytest.raises(fred.NeedsKey):
        fred.fetch(lambda *a, **k: b"", {})
    assert fred.parse_obs(json.dumps({"observations": [{"date": "d", "value": "."}, {"date": "e", "value": "1.5"}]}).encode()) == [("e", 1.5)]

    def failing(url, **k):
        raise RuntimeError("failed " + url)
    with pytest.raises(RuntimeError) as e:
        fred.fetch(failing, {"FRED_API_KEY": "SECRETKEY123"})
    assert "SECRETKEY123" not in str(e.value)
