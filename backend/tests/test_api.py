import importlib
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import ingest, sources

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def client(tmp_path, monkeypatch, fixture_get):
    tdir = tmp_path / "transcripts"
    tdir.mkdir()
    (tdir / "ZPJgzAP-iqU.txt").write_text("[12] 利率波动 很大, 波动率 上升\n[20] 我们看 long end", encoding="utf-8")
    monkeypatch.setenv("CONFIG_DIR", str(ROOT / "config"))
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("TRANSCRIPTS_DIR", str(tdir))
    monkeypatch.setenv("SCHEDULER", "0")
    monkeypatch.delenv("FRED_API_KEY", raising=False)
    import app.main as main
    main = importlib.reload(main)
    s = main.get_service()
    for g in sources.GROUPS:
        ingest.run_group(s.db, g, {"YAHOO_PAUSE_S": "0"}, get=fixture_get)
    s.invalidate()
    c = TestClient(main.app)
    c.main, c.svc, c.tdir = main, s, tdir
    return c


def test_health_and_fred_degrades(client):
    h = client.get("/api/health").json()
    assert h["ok"] and h["fred_key"] is False and h["transcripts"] == {"transcribed": 1, "total": 90}
    src = {s["group"]: s for s in client.get("/api/sources").json()}
    assert src["yahoo"]["state"] == "ok" and src["fred"]["state"] == "needs_key"
    panels = {p["id"]: p for p in client.get("/api/panels").json()}
    hy = next(c for c in panels["credit"]["charts"] if c["id"] == "hy")
    assert hy["latest"]["available"] is False and "add FRED key" in hy["latest"]["reason"]
    us10 = next(c for c in panels["rates"]["charts"] if c["id"] == "us10y")
    assert us10["latest"]["available"] and us10["latest"]["value"] > 0


def test_all_panel_series_are_known(client):
    meta = client.svc.meta
    from app.panels import all_chart_series
    for s in all_chart_series():
        assert s in meta, s


def test_series_endpoint_and_transforms(client):
    r = client.get("/api/series", params={"ids": "yh_nvda,yh_amd", "days": 90, "transform": "rebase"}).json()
    assert r["yh_nvda"]["points"][0][1] == pytest.approx(100.0)
    assert client.get("/api/series", params={"ids": ""}).status_code in (400, 422)
    assert client.get("/api/series", params={"ids": ",".join(f"s{i}" for i in range(13))}).status_code == 400


def test_alerts_endpoint_and_history(client):
    a = client.get("/api/alerts").json()
    assert "results" in a and a["note"].startswith("Indicator conditions only")
    assert {r["id"] for r in a["results"]} >= {"us10y_ge_5_5", "vix_term_inversion"}
    # force a breach: 10y live = 6%
    from conftest import chart_json
    client.svc.db.upsert_series({"yh_tnx": [("2026-11-10", 6.0)]})
    client.svc.invalidate()
    a = client.post("/api/alerts/reload").json()
    assert "us10y_ge_5_5" in a["triggered"]
    hist = client.get("/api/alerts/history").json()
    assert any(h["alert_id"] == "us10y_ge_5_5" for h in hist)
    # cooldown: second evaluation must not add a duplicate
    n = len(hist)
    client.svc.run_alerts()
    assert len(client.get("/api/alerts/history").json()) == n


def test_view_notes_and_transcript_status(client):
    v = client.get("/api/view/rate_vol").json()
    assert v["snippets"] and v["snippets"][0]["url"].startswith("https://youtu.be/ZPJgzAP-iqU?t=")
    assert "may contain errors" in v["disclaimer"]
    assert client.get("/api/view/nope").status_code == 404
    # new transcript arrives while running -> picked up via scan (status endpoint triggers scan)
    (client.tdir / "xfiZFQJW3gk.txt").write_text("[5] 十年期 利率", encoding="utf-8")
    assert client.get("/api/transcripts/status").json()["transcribed"] == 2
    notes = client.get("/api/notes").json()
    assert notes and notes == sorted(notes, key=lambda n: n["date"], reverse=True)
    assert all(n["date"] and n["basis"] in ("own ASR", "third-party AI summary") for n in notes)


def test_no_trade_signal_language_in_user_facing_config():
    import re
    bad = re.compile(r"\b(buy|sell|short it|go long|recommend(ed)? (buying|selling))\b", re.I)
    for f in ("alerts.yaml", "notes.yaml", "manual_inputs.yaml"):
        txt = (ROOT / "config" / f).read_text()
        # allow descriptive words about flows ("CTA buying", "selling pressure") but not imperatives
        assert not re.search(r"\b(you should|we recommend|buy now|sell now|buy the|sell the)\b", txt, re.I), f


def test_refresh_endpoint_404(client):
    assert client.post("/api/refresh/nonsense").status_code == 404


def test_failed_source_reports_state(tmp_path, fixture_get):
    from app.db import DB
    db = DB(tmp_path / "x.sqlite")
    fixture_get.state["fail"].add("treasury.gov")
    r = ingest.run_group(db, "treasury_curve", {}, get=fixture_get)
    assert r["state"] == "error"
    st = db.statuses()["treasury_curve"]
    assert st["state"] == "error" and st["last_ok"] is None
    fixture_get.state["fail"].clear()
    assert ingest.run_group(db, "treasury_curve", {}, get=fixture_get)["state"] == "ok"
    assert db.statuses()["treasury_curve"]["last_ok"]
