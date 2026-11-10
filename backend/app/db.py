from __future__ import annotations
import sqlite3
import threading
from datetime import datetime, timezone

SCHEMA = """
CREATE TABLE IF NOT EXISTS observations(series_id TEXT NOT NULL, ts TEXT NOT NULL, value REAL NOT NULL,
  PRIMARY KEY(series_id, ts));
CREATE TABLE IF NOT EXISTS fetch_status(grp TEXT PRIMARY KEY, last_attempt TEXT, last_ok TEXT, last_error TEXT,
  state TEXT, n_rows INTEGER DEFAULT 0, partial_errors TEXT);
CREATE TABLE IF NOT EXISTS alert_state(alert_id TEXT PRIMARY KEY, last_fired TEXT, last_value REAL, active INTEGER);
CREATE TABLE IF NOT EXISTS alert_history(id INTEGER PRIMARY KEY AUTOINCREMENT, fired_at TEXT, alert_id TEXT,
  metric TEXT, value REAL, threshold REAL, as_of TEXT, severity TEXT, basis TEXT, stale INTEGER, message TEXT);
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class DB:
    def __init__(self, path):
        self.path = str(path)
        self.lock = threading.RLock()
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        with self.lock:
            self.conn.executescript(SCHEMA)
            self.conn.commit()

    def upsert_series(self, series: dict) -> int:
        rows = [(sid, d, float(v)) for sid, pts in series.items() if not sid.startswith("__") for d, v in pts]
        with self.lock:
            self.conn.executemany("INSERT OR REPLACE INTO observations(series_id, ts, value) VALUES (?,?,?)", rows)
            self.conn.commit()
        return len(rows)

    def get_series(self, sid: str, since: str | None = None) -> list:
        q, a = "SELECT ts, value FROM observations WHERE series_id=?", [sid]
        if since:
            q += " AND ts>=?"
            a.append(since)
        with self.lock:
            return [(r["ts"], r["value"]) for r in self.conn.execute(q + " ORDER BY ts", a)]

    def all_series(self, ids=None, since: str | None = None) -> dict:
        with self.lock:
            if ids is None:
                ids = [r[0] for r in self.conn.execute("SELECT DISTINCT series_id FROM observations")]
        return {i: s for i in ids if (s := self.get_series(i, since))}

    def set_status(self, grp, state, n_rows=0, error=None, partial=None):
        t = now_iso()
        with self.lock:
            cur = self.conn.execute("SELECT last_ok FROM fetch_status WHERE grp=?", (grp,)).fetchone()
            last_ok = t if state in ("ok", "partial") else (cur["last_ok"] if cur else None)
            self.conn.execute("INSERT OR REPLACE INTO fetch_status VALUES (?,?,?,?,?,?,?)",
                              (grp, t, last_ok, error, state, n_rows, partial))
            self.conn.commit()

    def statuses(self) -> dict:
        with self.lock:
            return {r["grp"]: dict(r) for r in self.conn.execute("SELECT * FROM fetch_status")}

    def get_alert_state(self) -> dict:
        with self.lock:
            return {r["alert_id"]: {"last_fired": r["last_fired"], "last_value": r["last_value"],
                                    "active": bool(r["active"])}
                    for r in self.conn.execute("SELECT * FROM alert_state")}

    def save_alert_state(self, state: dict):
        with self.lock:
            for aid, s in state.items():
                self.conn.execute("INSERT OR REPLACE INTO alert_state VALUES (?,?,?,?)",
                                  (aid, s.get("last_fired"), s.get("last_value"), 1 if s.get("active") else 0))
            self.conn.commit()

    def add_history(self, res: dict):
        with self.lock:
            self.conn.execute(
                "INSERT INTO alert_history(fired_at, alert_id, metric, value, threshold, as_of, severity, basis, stale, message)"
                " VALUES (?,?,?,?,?,?,?,?,?,?)",
                (now_iso(), res["id"], res["metric"], res["value"], res["threshold"], res["as_of"], res["severity"],
                 res["basis"], 1 if res.get("stale") else 0, res["message"]))
            self.conn.commit()

    def history(self, limit=200) -> list:
        with self.lock:
            return [dict(r) for r in self.conn.execute("SELECT * FROM alert_history ORDER BY id DESC LIMIT ?", (limit,))]
