from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app import alerts_core, derived, ingest
from app.derived import compute_derived, ffill_align, pick

ROOT = Path(__file__).resolve().parents[2]
NOW = datetime(2026, 11, 10, 12, tzinfo=timezone.utc)


def daily(vals, end="2026-11-10"):
    e = datetime.strptime(end, "%Y-%m-%d")
    return [((e - timedelta(days=len(vals) - 1 - i)).strftime("%Y-%m-%d"), float(v)) for i, v in enumerate(vals)]


def test_pick_prefers_latest():
    s = {"a": [("2026-11-09", 1.0)], "b": [("2026-11-10", 2.0)]}
    assert pick(s, "a", "b")[-1][1] == 2.0 and pick(s, "a", "zz")[-1][1] == 1.0 and pick(s, "zz") == []


def test_ffill_align_carries_forward():
    a = [("2026-11-09", 5.0), ("2026-11-10", 6.0)]
    b = [("2026-11-08", 1.0)]
    assert ffill_align(a, b) == [("2026-11-09", 5.0, 1.0), ("2026-11-10", 6.0, 1.0)]


def test_derived_ratio_spread_crack_drawdown():
    base = {"yh_vix": daily([20, 22]), "yh_vix3m": daily([22, 20]), "yh_tnx": daily([4.9, 5.0]),
            "ust_2y": [("2026-11-09", 4.5)], "yh_ho": daily([3.0, 3.0]), "yh_brent": daily([90.0, 90.0]),
            "yh_spx": daily([100, 120, 108])}
    d = compute_derived(base)
    assert d["vix_term_ratio"][-1][1] == pytest.approx(1.1) and d["vix_term_ratio"][0][1] < 1
    assert d["curve_10y2y"][-1][1] == pytest.approx(0.5)
    assert d["diesel_crack"][-1][1] == pytest.approx(3.0 * 42 - 90)
    assert d["spx_drawdown_pct"][-1][1] == pytest.approx(-10.0)
    assert "hy_oas" not in d


def rules(*r):
    return list(r)


def R(**k):
    base = dict(id="r", metric="m", kind="level", op=">=", threshold=1, severity="high", basis="heuristic")
    base.update(k)
    return base


META = {"m": {"stale_days": 4, "source": "test"}}


def test_level_change_abs_change_pct():
    s = {"m": daily([100, 100, 100, 100, 100, 110])}
    out = alerts_core.evaluate([R(id="lv", threshold=105), R(id="ca", kind="change_abs", window_days=5, threshold=10),
                                R(id="cp", kind="change_pct", window_days=5, threshold=10, op=">="),
                                R(id="no", threshold=200)], s, META, NOW)
    by = {r["id"]: r for r in out}
    assert by["lv"]["triggered"] and by["ca"]["triggered"] and by["cp"]["triggered"] and not by["no"]["triggered"]
    assert by["ca"]["value"] == pytest.approx(10.0) and by["cp"]["value"] == pytest.approx(10.0)


def test_insufficient_history_and_missing_series_are_unavailable():
    out = alerts_core.evaluate([R(id="a", kind="change_abs", window_days=30, threshold=1), R(id="b", metric="nope")],
                               {"m": daily([1, 2, 3])}, META, NOW)
    assert [r["status"] for r in out] == ["unavailable", "unavailable"]
    assert "history" in out[0]["reason"]


def test_stale_flag_and_ops():
    s = {"m": daily([5, 5], end="2026-11-01")}
    r = alerts_core.evaluate([R(op="<=", threshold=5)], s, META, NOW)[0]
    assert r["triggered"] and r["stale"] is True
    r2 = alerts_core.evaluate([R(op="<", threshold=5)], s, META, NOW)[0]
    assert not r2["triggered"]


def test_cooldown_dedupes_and_expires():
    rl = [R(id="x", cooldown_hours=24)]
    res = alerts_core.evaluate(rl, {"m": daily([2, 2])}, META, NOW)
    state = {}
    fresh, supp = alerts_core.apply_cooldown(res, state, rl, {}, NOW)
    assert len(fresh) == 1 and not supp
    fresh, supp = alerts_core.apply_cooldown(res, state, rl, {}, NOW + timedelta(hours=3))
    assert not fresh and supp == ["x"]
    fresh, supp = alerts_core.apply_cooldown(res, state, rl, {}, NOW + timedelta(hours=25))
    assert len(fresh) == 1


def test_state_roundtrip(tmp_path):
    p = str(tmp_path / "s.json")
    assert alerts_core.load_state(p) == {}
    alerts_core.save_state(p, {"a": {"active": True}})
    assert alerts_core.load_state(p) == {"a": {"active": True}}
    (tmp_path / "bad.json").write_text("{nope")
    assert alerts_core.load_state(str(tmp_path / "bad.json")) == {}


def test_config_validation(tmp_path):
    f = tmp_path / "a.yaml"
    f.write_text("alerts:\n  - id: a\n    metric: m\n    op: \"=>\"\n    threshold: 1\n")
    with pytest.raises(ValueError):
        alerts_core.load_rules(str(f))
    f.write_text("alerts:\n  - id: a\n    metric: m\n    op: \">=\"\n    threshold: 1\n    kind: change_abs\n")
    with pytest.raises(ValueError):
        alerts_core.load_rules(str(f))


def test_default_alert_rules_are_wired_to_known_metrics():
    settings, rl = alerts_core.load_rules(str(ROOT / "config" / "alerts.yaml"))
    meta = ingest.all_meta()
    manual_ids = {f"manual_{m['id']}" for m in __import__("yaml").safe_load((ROOT / "config" / "manual_inputs.yaml").read_text())["manual"]}
    assert len(rl) >= 15
    for r in rl:
        assert r["metric"] in meta or r["metric"] in manual_ids, r["id"]
        assert r["basis"], r["id"]
    ids = [r["id"] for r in rl]
    assert len(ids) == len(set(ids))
    assert "gex_negative" in settings["disabled_ids"]
    by = {r["id"]: r for r in rl}
    assert by["us10y_ge_5_5"]["threshold"] == 5.5 and by["us10y_ge_5_5"]["basis"].startswith("his stated")
