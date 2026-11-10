from __future__ import annotations
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from . import ingest, sources
from .service import Service
from .settings import Settings

log = logging.getLogger("app")
logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))

settings = Settings()
svc: Service | None = None
scheduler = None


def get_service() -> Service:
    global svc
    if svc is None:
        svc = Service(settings)
    return svc


def _refresh_group(g: str):
    s = get_service()
    r = ingest.run_group(s.db, g, dict(settings.env, FRED_API_KEY=settings.fred_key))
    s.invalidate()
    s.run_alerts()
    return r


@asynccontextmanager
async def lifespan(app: FastAPI):
    global scheduler
    s = get_service()
    if settings.scheduler_enabled:
        from apscheduler.schedulers.background import BackgroundScheduler
        from datetime import datetime, timedelta
        scheduler = BackgroundScheduler(timezone="UTC")
        groups = settings.groups_enabled or list(sources.GROUPS)
        for i, g in enumerate(groups):
            iv = max(1, int(sources.GROUPS[g]["interval"] * settings.interval_scale))
            scheduler.add_job(_refresh_group, "interval", minutes=iv, args=[g], id=f"grp_{g}", max_instances=1,
                              coalesce=True, next_run_time=datetime.utcnow() + timedelta(seconds=3 + 4 * i))
        scheduler.add_job(lambda: (s.tindex.scan(), s.invalidate()), "interval",
                          minutes=settings.transcript_scan_minutes, id="transcripts", max_instances=1)
        scheduler.start()
    yield
    if scheduler:
        scheduler.shutdown(wait=False)


app = FastAPI(title="Shanghao dashboard", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET", "POST"], allow_headers=["*"])


@app.get("/api/health")
def health():
    s = get_service()
    return {"ok": True, "fred_key": bool(settings.fred_key), "scheduler": settings.scheduler_enabled,
            "transcripts": {k: v for k, v in s.tindex.status().items() if k in ("transcribed", "total")}}


@app.get("/api/overview")
def overview():
    s = get_service()
    full = s.full_series()
    keys = ["us10y", "vix", "vix_term_ratio", "spx", "brent", "usdjpy", "btc", "net_gex"]
    tiles = [s._chart_series_info(k, full) for k in keys]
    al = s.alerts()
    return {"tiles": tiles, "alerts": {"triggered_count": al["triggered_count"], "triggered": al["triggered"],
                                        "evaluated_at": al["evaluated_at"]},
            "sources": s.source_status(), "transcripts": {k: v for k, v in s.tindex.status().items()
                                                           if k in ("transcribed", "total")}}


@app.get("/api/panels")
def panels():
    return get_service().panels()


@app.get("/api/series")
def series(ids: str = Query(...), days: int = 365, transform: str | None = None):
    sid_list = [i for i in ids.split(",") if i]
    if not sid_list or len(sid_list) > 12:
        raise HTTPException(400, "1-12 series ids")
    return get_service().series_data(sid_list, min(days, 5000), transform)


@app.get("/api/alerts")
def alerts():
    return get_service().alerts()


@app.get("/api/alerts/history")
def alerts_history(limit: int = 200):
    return get_service().db.history(min(limit, 1000))


@app.post("/api/alerts/reload")
def alerts_reload():
    s = get_service()
    s.reload_config()
    s.run_alerts()
    return s.alerts()


@app.get("/api/sources")
def source_status():
    return get_service().source_status()


@app.post("/api/refresh/{group}")
def refresh(group: str):
    if group not in sources.GROUPS:
        raise HTTPException(404, "unknown group")
    return _refresh_group(group)


@app.get("/api/view")
def view_indicators():
    return get_service().view_indicators()


@app.get("/api/view/{key}")
def view(key: str, limit: int = 6):
    r = get_service().view(key, min(limit, 30))
    if r is None:
        raise HTTPException(404, "unknown indicator")
    return r


@app.get("/api/notes")
def notes():
    return get_service().notes_feed()


@app.get("/api/transcripts/status")
def transcripts_status():
    s = get_service()
    s.tindex.scan()
    return s.tindex.status()
