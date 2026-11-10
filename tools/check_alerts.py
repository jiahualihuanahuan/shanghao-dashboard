#!/usr/bin/env python3
"""Standalone threshold-alert check. Python 3.9+ standard library only; public data only.

    python3 tools/check_alerts.py                       # evaluate config/alerts.yaml, print JSON
    python3 tools/check_alerts.py --state /tmp/alerts_state.json   # remember what was already reported (cooldown)
    FRED_API_KEY=... python3 tools/check_alerts.py      # optional: enables the FRED-based rules (HY/CCC/unemployment)

Uses the exact same adapters and evaluator as the dashboard (backend/app). Prints one JSON object:
  triggered   - alerts to report now (new, or cooldown elapsed)
  ongoing     - ids still breached but within their cooldown (already reported)
  unavailable - rules that could not be evaluated (no key / no data / source error)
  checked     - every rule's current status (use --all to include)
Indicator conditions only - not buy/sell signals."""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app import alerts_core, collect, derived, ingest  # noqa: E402


def run(config: Path, manual: Path | None, state_path: str | None, env: dict, get=None, now=None) -> dict:
    now = now or datetime.now(timezone.utc)
    settings, rules = alerts_core.load_rules(str(config))
    metrics = [r["metric"] for r in rules]
    man_series, man_meta = ingest.load_manual(manual) if manual and manual.exists() else ({}, {})
    fetch_metrics = [m for m in metrics if not m.startswith("manual_")]
    kw = {"get": get} if get else {}
    base, errors, unavailable_groups = collect.collect(fetch_metrics, env, **kw)
    base.update(man_series)
    full = derived.compute_derived(base)
    meta = ingest.all_meta()
    meta.update(man_meta)
    results = alerts_core.evaluate(rules, full, meta, now, settings)
    state = alerts_core.load_state(state_path)
    fresh, suppressed = alerts_core.apply_cooldown(results, state, rules, settings, now)
    alerts_core.save_state(state_path, state)
    return {
        "generated_at": now.isoformat(timespec="seconds"),
        "rules": len(rules),
        "triggered": fresh,
        "ongoing": suppressed,
        "unavailable": [{"id": r["id"], "metric": r["metric"], "reason": r["reason"]} for r in results
                        if r["status"] == "unavailable"],
        "source_errors": errors,
        "sources_without_key": unavailable_groups,
        "checked": [{k: r[k] for k in ("id", "metric", "status", "value", "as_of", "threshold", "stale")}
                    for r in results],
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default=str(ROOT / "config" / "alerts.yaml"))
    ap.add_argument("--manual", default=str(ROOT / "config" / "manual_inputs.yaml"))
    ap.add_argument("--state", default=None, help="JSON file remembering fired alerts (enables cooldown dedupe)")
    ap.add_argument("--all", action="store_true", help="include every rule's status under 'checked'")
    ap.add_argument("--exit-code", action="store_true", help="exit 2 when something is triggered")
    a = ap.parse_args(argv)
    out = run(Path(a.config), Path(a.manual), a.state, dict(os.environ))
    if not a.all:
        out.pop("checked")
    json.dump(out, sys.stdout, indent=2, ensure_ascii=False)
    print()
    return 2 if (a.exit_code and out["triggered"]) else 0


if __name__ == "__main__":
    sys.exit(main())
