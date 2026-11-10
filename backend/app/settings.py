from __future__ import annotations
import os
from pathlib import Path


class Settings:
    def __init__(self, env=None):
        e = env if env is not None else os.environ
        self.env = e
        self.config_dir = Path(e.get("CONFIG_DIR", "/app/config"))
        self.data_dir = Path(e.get("DATA_DIR", "/data"))
        self.transcripts_dir = Path(e.get("TRANSCRIPTS_DIR", "/data/transcripts"))
        self.db_path = Path(e.get("DB_PATH", str(self.data_dir / "dashboard.sqlite")))
        self.fred_key = (e.get("FRED_API_KEY") or "").strip()
        self.scheduler_enabled = e.get("SCHEDULER", "1") not in ("0", "false", "no")
        self.interval_scale = float(e.get("REFRESH_SCALE", "1"))  # 2 = half as often
        self.groups_enabled = [g for g in (e.get("GROUPS", "") or "").split(",") if g]
        self.transcript_scan_minutes = int(e.get("TRANSCRIPT_SCAN_MINUTES", "5"))
