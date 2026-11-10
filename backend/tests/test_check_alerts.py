import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import check_alerts

ROOT = Path(__file__).resolve().parents[2]
CFG = ROOT / "config" / "alerts.yaml"
MAN = ROOT / "config" / "manual_inputs.yaml"


def test_script_reports_breach_then_dedupes(tmp_path, fixture_get):
    fixture_get.state["yahoo"]["^TNX"] = [4.8] * 259 + [5.7]   # >= 5.5 and +0.4 in 28d
    fixture_get.state["yahoo"]["^VIX"] = [20.0] * 259 + [26.0]
    fixture_get.state["yahoo"]["^VIX3M"] = [22.0] * 259 + [23.0]                          # ratio 1.13 -> inverted
    state = str(tmp_path / "state.json")
    env = {"YAHOO_PAUSE_S": "0"}
    out = check_alerts.run(CFG, MAN, state, env, get=fixture_get)
    ids = {a["id"] for a in out["triggered"]}
    assert {"us10y_ge_5_5", "us10y_fast_rise", "vix_term_inversion"} <= ids
    for a in out["triggered"]:       # contract used by the scheduled routine
        assert {"id", "metric", "value", "threshold", "as_of", "source", "stale", "message", "basis"} <= set(a)
    assert any(g["group"] == "fred" for g in out["sources_without_key"])
    assert {u["metric"] for u in out["unavailable"]} >= {"hy_oas", "ccc_oas", "unrate", "manual_fwd_pe_sp500"}
    json.dumps(out)                                          # must be JSON-serialisable
    out2 = check_alerts.run(CFG, MAN, state, env, get=fixture_get)
    assert not out2["triggered"] and "us10y_ge_5_5" in out2["ongoing"]       # cooldown dedupe
    out3 = check_alerts.run(CFG, MAN, None, env, get=fixture_get)            # no state file -> reports again
    assert "us10y_ge_5_5" in {a["id"] for a in out3["triggered"]}


def test_script_survives_source_failure(fixture_get):
    fixture_get.state["fail"].add("finance.yahoo.com")
    out = check_alerts.run(CFG, MAN, None, {"YAHOO_PAUSE_S": "0"}, get=fixture_get)
    assert any(e["group"] == "yahoo" for e in out["source_errors"])
    # best-of fallbacks: 10Y falls back to the Treasury curve, VIX to the Cboe CSV, so those rules still evaluate
    assert not {"us10y_ge_5_5", "vix_ge_30", "vix_term_inversion"} & {u["id"] for u in out["unavailable"]}
    assert any(u["metric"] in ("brent", "diesel_crack", "sox") for u in out["unavailable"])
    assert out["rules"] >= 15


def test_fred_rules_work_with_key(fixture_get):
    out = check_alerts.run(CFG, MAN, None, {"FRED_API_KEY": "k", "YAHOO_PAUSE_S": "0"}, get=fixture_get)
    assert not any(g["group"] == "fred" for g in out["sources_without_key"])


def test_cli_help_runs_with_stdlib_only():
    r = subprocess.run([sys.executable, "-S", str(ROOT / "tools" / "check_alerts.py"), "--help"], capture_output=True, text=True)
    assert r.returncode == 0 and "standard library" in r.stdout
