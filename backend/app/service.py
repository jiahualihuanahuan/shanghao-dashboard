"""Application state shared by the API and the scheduler (kept free of FastAPI so it is unit-testable)."""
from __future__ import annotations
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

from . import alerts_core, derived, ingest, sources
from .db import DB, now_iso
from .panels import PANELS
from .settings import Settings
from .transcripts import TranscriptIndex, load_videos, DISCLAIMER


def transform(series: list, how: str | None) -> list:
    if not series or not how:
        return series
    if how == "yoy":
        return [(series[i][0], (series[i][1] / series[i - 12][1] - 1) * 100) for i in range(12, len(series))
                if series[i - 12][1]]
    if how == "diff12":
        return [(series[i][0], series[i][1] - series[i - 12][1]) for i in range(12, len(series))]
    if how == "mom":
        return [(series[i][0], series[i][1] - series[i - 1][1]) for i in range(1, len(series))]
    if how == "rebase":
        b = series[0][1]
        return [(d, v / b * 100) for d, v in series] if b else series
    return series


class Service:
    def __init__(self, settings: Settings, get=None):
        self.s = settings
        self.get = get
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        self.db = DB(settings.db_path)
        self.meta = ingest.all_meta()
        self._cache = (0.0, None)
        self._lock = threading.RLock()
        self.reload_config()
        self.last_alerts = None

    # ---- config ------------------------------------------------------
    def reload_config(self):
        cd = self.s.config_dir
        ind = yaml.safe_load((cd / "indicators.yaml").read_text(encoding="utf-8"))
        self.topics = ind.get("topics", {})
        self.indicators = ind.get("indicators", {})
        self.notes = (yaml.safe_load((cd / "notes.yaml").read_text(encoding="utf-8")) or {}).get("notes", [])
        self.videos = load_videos(cd / "videos.csv")
        self.tindex = TranscriptIndex(self.s.transcripts_dir, self.videos, self.indicators)
        self.tindex.scan()
        _, self.manual_meta = ingest.load_manual(cd / "manual_inputs.yaml")
        self.meta.update(self.manual_meta)
        self._cache = (0.0, None)

    # ---- data --------------------------------------------------------
    def full_series(self) -> dict:
        with self._lock:
            t, val = self._cache
            if val is not None and time.time() - t < 20:
                return val
            base = self.db.all_series()
            man, _ = ingest.load_manual(self.s.config_dir / "manual_inputs.yaml")
            base.update(man)
            val = derived.compute_derived(base)
            self._cache = (time.time(), val)
            return val

    def invalidate(self):
        self._cache = (0.0, None)

    def _chart_series_info(self, sid: str, full: dict) -> dict:
        m = self.meta.get(sid, {"label": sid, "unit": "", "decimals": 2, "stale_days": 5, "source": "", "group": ""})
        s = full.get(sid) or []
        info = dict(id=sid, label=m["label"], unit=m["unit"], decimals=m["decimals"], source=m["source"],
                    available=bool(s), as_of=None, value=None, prev=None, change=None, change_pct=None, stale=None,
                    reason=None)
        group = m.get("group")
        if not s:
            info["reason"] = self.empty_reason(sid)
            return info
        d, v = s[-1]
        info.update(as_of=d, value=round(v, 6))
        if len(s) > 1:
            info.update(prev=s[-2][1], change=round(v - s[-2][1], 6),
                        change_pct=round((v / s[-2][1] - 1) * 100, 3) if s[-2][1] else None)
        age = (datetime.now(timezone.utc).date() - datetime.strptime(d, "%Y-%m-%d").date()).days
        info["stale"] = age > m["stale_days"]
        return info

    def empty_reason(self, sid: str) -> str:
        m = self.meta.get(sid, {})
        if m.get("group") == "manual" or sid.startswith("manual_"):
            return "enter a value in config/manual_inputs.yaml"
        deps = m.get("deps") or [sid]
        groups = {self.meta.get(d, {}).get("group") for d in deps}
        st = self.db.statuses()
        if "fred" in groups and (st.get("fred", {}).get("state") == "needs_key" or not self.s.fred_key):
            return "add FRED key (FRED_API_KEY in .env)"
        for g in groups:
            row = st.get(g)
            if row and row["state"] == "error":
                return f"source error: {row['last_error']}"
        return "no data yet (waiting for first refresh)"

    def panels(self) -> list:
        full = self.full_series()
        out = []
        for p in PANELS:
            charts = []
            for c in p["charts"]:
                infos = [self._chart_series_info(s, full) for s in c["series"]]
                charts.append({**c, "latest": infos[0], "members": infos})
            out.append({"id": p["id"], "title": p["title"], "topic": p["topic"],
                        "topic_name": self.topics.get(p["topic"], ""), "charts": charts})
        return out

    def series_data(self, sid_list: list, days: int, how: str | None) -> dict:
        full = self.full_series()
        since = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
        out = {}
        for sid in sid_list:
            s = full.get(sid) or []
            if how in ("yoy", "diff12", "mom"):
                s = transform(s, how)
            s = [(d, v) for d, v in s if d >= since]
            if how == "rebase":
                s = transform(s, how)
            out[sid] = {"label": self.meta.get(sid, {}).get("label", sid), "points": [[d, round(v, 6)] for d, v in s]}
        return out

    # ---- alerts ------------------------------------------------------
    def run_alerts(self) -> dict:
        self.last_alerts = ingest.evaluate_alerts(self.db, self.s, self.s.config_dir)
        return self.last_alerts

    def alerts(self) -> dict:
        res = self.last_alerts or self.run_alerts()
        trig = [r for r in res["results"] if r["triggered"]]
        return {**res, "triggered_count": len(trig), "triggered": [r["id"] for r in trig],
                "note": "Indicator conditions only - not trade signals. basis = 'his stated level' or 'heuristic'."}

    # ---- sources -----------------------------------------------------
    def source_status(self) -> list:
        st = self.db.statuses()
        now = datetime.now(timezone.utc)
        out = []
        for g, spec in sources.GROUPS.items():
            row = st.get(g)
            age = None
            if row and row.get("last_ok"):
                age = int((now - datetime.fromisoformat(row["last_ok"])).total_seconds() // 60)
            state = row["state"] if row else "pending"
            if state == "needs_key" or (spec["key"] and not self.s.fred_key and state == "pending"):
                state = "needs_key"
            stale = age is not None and age > spec["interval"] * 3 + 5
            out.append(dict(group=g, label=spec["label"], interval_min=spec["interval"], state=state,
                            last_ok=row["last_ok"] if row else None, age_min=age, stale=stale,
                            error=row["last_error"] if row else None, partial=row["partial_errors"] if row else None,
                            needs=spec["key"], series=len(spec["series"])))
        return out

    # ---- view / notes -----------------------------------------------
    def view_indicators(self) -> list:
        return [{"key": k, "title": v["title"], "topic": v["topic"], "topic_name": self.topics.get(v["topic"], ""),
                 "episodes_matched": self.tindex.coverage(k)} for k, v in self.indicators.items()]

    def view(self, key: str, limit: int = 6) -> dict:
        ind = self.indicators.get(key)
        if not ind:
            return None
        return {"key": key, "title": ind["title"], "topic": ind["topic"], "disclaimer": DISCLAIMER,
                "transcripts": {k: v for k, v in self.tindex.status().items() if k in ("transcribed", "total")},
                "snippets": self.tindex.search(key, limit=limit)}

    def notes_feed(self) -> list:
        out = []
        for n in self.notes:
            v = self.videos.get(n["episode"], {})
            out.append({**n, "date": v.get("date", ""), "title": v.get("title", n["episode"]),
                        "topic_name": self.topics.get(n["topic"], ""), "url": f"https://youtu.be/{n['episode']}"})
        out.sort(key=lambda x: x["date"], reverse=True)
        return out
