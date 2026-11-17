#!/usr/bin/env python3
"""Split a combined Whisper transcript export (markdown) into <video_id>.txt files for the Shanghao view.

Input: one markdown file with one section per episode, headed "## <title>" (the video title / file name, e.g.
"## 市场概述2025年4月15日" or "## 2024年 11月5日"), followed by the plain transcript text (no timestamps).
Titles are matched to config/videos.csv (whitespace-insensitive). Output lines are untimed (see app/transcripts.py),
so snippets from these files link to the start of the video.

Standard library only. Nothing is uploaded; transcripts stay out of git (.gitignore: transcripts/).

    python3 tools/import_transcripts_md.py all_transcripts.md --out transcripts            # fill missing only
    python3 tools/import_transcripts_md.py all_transcripts.md --out transcripts --replace  # overwrite existing files
    python3 tools/import_transcripts_md.py all.md --out t --assign "市场概述2026年4月21日=PweaTXhs-aU"

Duplicate titles in videos.csv (e.g. two uploads both titled "市场概述2026年4月21日") are resolved with --assign or,
failing that, automatically by text overlap with an existing timed transcript of each candidate in --out / --compare.
Prints a JSON summary (written, skipped, unmatched, ambiguous) to stdout.
"""
from __future__ import annotations
import argparse
import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CN_DATE = re.compile(r"(?:(\d{4})\s*年)?\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日")
SPLIT = re.compile(r"(?<=[。！？!?；;，,])|\s+")


def norm(title: str) -> str:
    return re.sub(r"\s+", "", title)


def title_date(title: str) -> str | None:
    """ISO date written in a title ("2024年 11月5日" -> 2024-11-05). Titles can be wrong (see videos.csv)."""
    m = CN_DATE.search(title)
    if not m:
        return None
    y, mo, d = m.groups()
    return f"{y}-{int(mo):02d}-{int(d):02d}" if y else f"????-{int(mo):02d}-{int(d):02d}"


def parse_sections(text: str) -> list[tuple[str, str]]:
    parts = re.split(r"^##[ \t]+(.+?)[ \t]*$", text, flags=re.M)
    return [(parts[i].strip(), parts[i + 1].strip()) for i in range(1, len(parts) - 1, 2)]


def to_lines(body: str, target: int = 40) -> list[str]:
    """Group short ASR phrases into lines of roughly `target` characters (one line = one search unit)."""
    out, cur = [], ""
    for ph in (p.strip() for p in SPLIT.split(body)):
        if not ph:
            continue
        cur = f"{cur} {ph}".strip() if cur else ph
        if len(cur) >= target:
            out.append(cur)
            cur = ""
    if cur:
        out.append(cur)
    return out


def _grams(s: str, n: int = 4) -> set:
    s = re.sub(r"[\s\[\]\d]+", "", s)
    return {s[i:i + n] for i in range(max(0, len(s) - n + 1))}


def resolve(body: str, cands: list[dict], dirs: list[Path]) -> str | None:
    g = _grams(body[:5000])
    scores = []
    for c in cands:
        best = 0.0
        for d in dirs:
            p = d / f"{c['id']}.txt"
            if p.exists() and g:
                best = max(best, len(g & _grams(p.read_text(encoding="utf-8", errors="replace")[:12000])) / len(g))
        scores.append((best, c["id"]))
    scores.sort(reverse=True)
    if scores and scores[0][0] > 0.02 and (len(scores) == 1 or scores[0][0] >= 1.5 * max(scores[1][0], 1e-9)):
        return scores[0][1]
    return None


def is_timed(p: Path) -> bool:
    try:
        with open(p, encoding="utf-8", errors="replace") as f:
            for ln in f:
                if ln.strip():
                    return bool(re.match(r"^\[\d+\]", ln.strip()))
    except OSError:
        pass
    return False


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("markdown")
    ap.add_argument("--out", required=True, help="transcripts folder (TRANSCRIPTS_HOST_PATH)")
    ap.add_argument("--videos", default=str(ROOT / "config" / "videos.csv"))
    ap.add_argument("--replace", action="store_true", help="overwrite existing files (default: only fill missing ids)")
    ap.add_argument("--assign", action="append", default=[], help='"<title>=<video_id>" for duplicate titles')
    ap.add_argument("--compare", action="append", default=[], help="extra folder of timed transcripts used to resolve duplicates")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)

    with open(a.videos, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    by_title: dict[str, list] = {}
    for r in rows:
        by_title.setdefault(norm(r["title"]), []).append(r)
    assign = {}
    for s in a.assign:
        t, _, vid = s.rpartition("=")
        assign[norm(t)] = vid.strip()
    out = Path(a.out)
    dirs = [out] + [Path(d) for d in a.compare]
    summary = {"sections": 0, "written": [], "skipped_existing": [], "unmatched": [], "ambiguous": []}
    seen = set()
    for title, body in parse_sections(Path(a.markdown).read_text(encoding="utf-8")):
        summary["sections"] += 1
        cands = by_title.get(norm(title), [])
        vid = assign.get(norm(title))
        if not vid and len(cands) == 1:
            vid = cands[0]["id"]
        elif not vid and len(cands) > 1:
            vid = resolve(body, cands, dirs)
            if not vid:
                summary["ambiguous"].append({"title": title, "candidates": [c["id"] for c in cands]})
                continue
        if not vid:
            summary["unmatched"].append({"title": title, "title_date": title_date(title)})
            continue
        if vid in seen:
            summary["ambiguous"].append({"title": title, "candidates": [vid], "note": "id already used"})
            continue
        seen.add(vid)
        meta = next((r for r in rows if r["id"] == vid), {})
        target = out / f"{vid}.txt"
        if target.exists() and target.stat().st_size and not a.replace:
            summary["skipped_existing"].append({"id": vid, "timed": is_timed(target)})
            continue
        lines = to_lines(body)
        if not a.dry_run:
            out.mkdir(parents=True, exist_ok=True)
            hdr = f"# {vid} | {meta.get('date', '')} | {title} | imported from {Path(a.markdown).name} (untimed ASR)\n"
            tmp = target.with_suffix(".tmp")
            tmp.write_text(hdr + "\n".join(lines) + "\n", encoding="utf-8")
            tmp.replace(target)   # atomic, so the app never indexes a half-written file
        summary["written"].append({"id": vid, "date": meta.get("date", ""), "lines": len(lines)})
    summary["written"].sort(key=lambda x: x["date"])
    missing = sorted({r["id"] for r in rows} - seen)
    summary["videos_without_section"] = [{"id": i, "title": next(r["title"] for r in rows if r["id"] == i)} for i in missing]
    json.dump(summary, sys.stdout, ensure_ascii=False, indent=1)
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
