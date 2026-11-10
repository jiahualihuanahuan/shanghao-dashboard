from __future__ import annotations
import logging
from datetime import datetime, timezone
from pathlib import Path

from . import alerts_core, derived, sources
from .collect import needed_base
from .db import DB
from .http import get as default_get
from .sources.fred import NeedsKey
from .yamlmini import load as load_yaml_mini

log = logging.getLogger("ingest")


def run_group(db: DB, group: str, env: dict, get=default_get) -> dict:
    spec = sources.GROUPS[group]
    if spec["key"] and not (env.get(spec["key"]) or "").strip():
        db.set_status(group, "needs_key", error=f"{spec['key']} not set")
        return {"group": group, "state": "needs_key"}
    try:
        res = spec["fetch"](get, env)
    except NeedsKey as e:
        db.set_status(group, "needs_key", error=str(e))
        return {"group": group, "state": "needs_key"}
    except Exception as e:
        log.warning("group %s failed: %s", group, e)
        db.set_status(group, "error", error=str(e)[:300])
        return {"group": group, "state": "error", "error": str(e)}
    partial = res.pop("__errors__", None)
    n = db.upsert_series(res)
    db.set_status(group, "partial" if partial else "ok", n_rows=n, partial="; ".join(partial)[:500] if partial else None)
    return {"group": group, "state": "partial" if partial else "ok", "rows": n}


def load_manual(path: Path) -> tuple[dict, dict]:
    """Manual inputs -> (series map, meta). Entries without value are skipped."""
    series, meta = {}, {}
    if not Path(path).exists():
        return series, meta
    for m in load_yaml_mini(str(path)).get("manual", []):
        sid = f"manual_{m['id']}"
        meta[sid] = dict(id=sid, label=m.get("label", sid), unit=m.get("unit", ""), decimals=2,
                         stale_days=int(m.get("stale_days") or 30), source="manual input (config/manual_inputs.yaml)",
                         group="manual", derived=False, note=m.get("note"))
        if m.get("value") is not None and m.get("as_of"):
            series[sid] = [(str(m["as_of"])[:10], float(m["value"]))]
    return series, meta


def all_meta() -> dict:
    meta = sources.series_meta()
    meta.update(derived.derived_meta())
    return meta


def evaluate_alerts(db: DB, settings, config_dir: Path, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    cfg, rules = alerts_core.load_rules(str(config_dir / "alerts.yaml"))
    meta = all_meta()
    man_series, man_meta = load_manual(config_dir / "manual_inputs.yaml")
    meta.update(man_meta)
    need = needed_base([r["metric"] for r in rules])
    base = db.all_series([n for n in need if not n.startswith("manual_")])
    base.update(man_series)
    full = derived.compute_derived(base)
    results = alerts_core.evaluate(rules, full, meta, now, cfg)
    state = db.get_alert_state()
    fresh, suppressed = alerts_core.apply_cooldown(results, state, rules, cfg, now)
    for r in fresh:
        db.add_history(r)
    db.save_alert_state(state)
    for r in results:
        r["new"] = any(f["id"] == r["id"] for f in fresh)
        r["in_cooldown"] = r["id"] in suppressed
    return {"evaluated_at": now.isoformat(timespec="seconds"), "results": results, "new": [r["id"] for r in fresh]}
