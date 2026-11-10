"""Threshold-alert evaluator shared by the app and tools/check_alerts.py. Stdlib only. No trade signals:
alerts describe indicator conditions that the YouTuber discussed, nothing more."""
from __future__ import annotations
import json
import operator
import os
from datetime import datetime, timedelta, timezone

from . import yamlmini

OPS = {">=": operator.ge, "<=": operator.le, ">": operator.gt, "<": operator.lt}
KINDS = ("level", "change_abs", "change_pct")


def load_rules(path: str):
    doc = yamlmini.load(path)
    settings = {"cooldown_hours": 24, "default_stale_days": 5}
    for k, v in doc.items():
        if k != "alerts" and not isinstance(v, list):
            settings[k] = v
    all_rules = doc.get("alerts") or []
    settings["disabled_ids"] = [r.get("id") for r in all_rules if r.get("enabled") is False]
    rules = [r for r in all_rules if r.get("enabled") is not False]
    for r in rules:
        for req in ("id", "metric", "op", "threshold"):
            if r.get(req) is None:
                raise ValueError(f"alert rule missing '{req}': {r}")
        if r["op"] not in OPS:
            raise ValueError(f"alert {r['id']}: bad op {r['op']}")
        r.setdefault("kind", "level")
        if r["kind"] not in KINDS:
            raise ValueError(f"alert {r['id']}: bad kind {r['kind']}")
        if r["kind"] != "level" and not r.get("window_days"):
            raise ValueError(f"alert {r['id']}: window_days required for {r['kind']}")
    return settings, rules


def _parse(d: str) -> datetime:
    return datetime.strptime(d[:10], "%Y-%m-%d")


def measure(series: list, rule: dict):
    """Return (value, as_of) or (None, reason)."""
    if not series:
        return None, "no data"
    as_of, last = series[-1]
    kind = rule.get("kind", "level")
    if kind == "level":
        return last, as_of
    cutoff = _parse(as_of) - timedelta(days=int(rule["window_days"]))
    base = None
    for d, v in series:
        if _parse(d) <= cutoff:
            base = v
        else:
            break
    if base is None:
        return None, f"need >= {rule['window_days']}d of history"
    if kind == "change_abs":
        return last - base, as_of
    if base == 0:
        return None, "zero base"
    return (last / base - 1.0) * 100.0, as_of


def evaluate(rules: list, series: dict, meta: dict, now: datetime | None = None, settings: dict | None = None):
    """series: base+derived series map. meta: id -> {stale_days, source, label, unit}. Returns list of result dicts."""
    now = now or datetime.now(timezone.utc)
    settings = settings or {}
    out = []
    for r in rules:
        m = meta.get(r["metric"], {})
        res = dict(id=r["id"], metric=r["metric"], kind=r["kind"], op=r["op"], threshold=r["threshold"],
                   window_days=r.get("window_days"), severity=r.get("severity", "medium"),
                   basis=r.get("basis", ""), source=m.get("source", ""), value=None, as_of=None, stale=None,
                   triggered=False, status="unavailable", message="", reason=None)
        val, as_of = measure(series.get(r["metric"]) or [], r)
        if val is None:
            res["reason"] = as_of
            res["message"] = f"{r['metric']}: unavailable ({as_of})"
            out.append(res)
            continue
        stale_days = m.get("stale_days", settings.get("default_stale_days", 5))
        age = (now.replace(tzinfo=None) - _parse(as_of)).days
        res.update(value=round(val, 4), as_of=as_of, stale=age > stale_days)
        res["triggered"] = bool(OPS[r["op"]](val, r["threshold"]))
        res["status"] = "triggered" if res["triggered"] else "ok"
        tmpl = r.get("message") or "{metric} {kind} {value} {op} {threshold}"
        try:
            res["message"] = tmpl.format(value=f"{val:.2f}", threshold=r["threshold"], as_of=as_of, metric=r["metric"],
                                         kind=r["kind"], op=r["op"], window_days=r.get("window_days"))
        except (KeyError, IndexError):
            res["message"] = tmpl
        out.append(res)
    return out


def apply_cooldown(results: list, state: dict, rules: list, settings: dict, now: datetime | None = None):
    """Split triggered results into new (emit) vs suppressed (still within cooldown). Mutates `state`."""
    now = now or datetime.now(timezone.utc)
    by_id = {r["id"]: r for r in rules}
    fresh, suppressed = [], []
    for res in results:
        st = state.setdefault(res["id"], {})
        if not res["triggered"]:
            st["active"] = False
            continue
        cd = float(by_id[res["id"]].get("cooldown_hours", settings.get("cooldown_hours", 24)))
        last = st.get("last_fired")
        due = True
        if last:
            due = now - datetime.fromisoformat(last) >= timedelta(hours=cd)
        if due:
            st.update(last_fired=now.isoformat(), last_value=res["value"], active=True)
            fresh.append(res)
        else:
            st["active"] = True
            suppressed.append(res["id"])
    return fresh, suppressed


def load_state(path: str | None) -> dict:
    if path and os.path.exists(path):
        try:
            with open(path) as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_state(path: str | None, state: dict):
    if path:
        tmp = path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(state, f, indent=1)
        os.replace(tmp, path)
