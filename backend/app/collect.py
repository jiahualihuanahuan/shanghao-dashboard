"""Fetch only what a set of metrics needs (used by tools/check_alerts.py). Stdlib only."""
from __future__ import annotations
from . import derived, sources
from .http import get as default_get
from .sources import yahoo


def needed_base(metrics) -> set:
    need = set()
    for m in metrics:
        need.update(derived.deps_for(m))
    return need


def collect(metrics, env, get=default_get):
    """Returns (base_series_map, errors, unavailable_groups)."""
    need = needed_base(metrics)
    base, errors, unavailable = {}, [], []
    for g, spec in sources.GROUPS.items():
        ids = [s[0] for s in spec["series"] if s[0] in need]
        if not ids:
            continue
        if spec["key"] and not (env.get(spec["key"]) or "").strip():
            unavailable.append({"group": g, "reason": f"{spec['key']} not set"})
            continue
        try:
            if g == "yahoo":
                res = yahoo.fetch(get, env, only=set(ids), pause=0.2)
            else:
                res = spec["fetch"](get, env)
        except Exception as e:
            errors.append({"group": g, "error": str(e)[:200]})
            continue
        for k, v in res.items():
            if k == "__errors__":
                errors.extend({"group": g, "error": x[:200]} for x in v)
            elif k in need:
                base[k] = v
    return base, errors, unavailable
