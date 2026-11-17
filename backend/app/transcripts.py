"""Transcript index behind the "Shanghao view" panel.

Reads /data/transcripts/<video_id>.txt, re-scans by mtime so files that arrive while the app runs are picked up.
Two line formats are accepted (they can be mixed, one per file is typical):
  * timed:   "[123] text"  (seconds from start)  -> snippets link to youtu.be/<id>?t=123
  * untimed: "text"        (e.g. imported from a Whisper text/markdown export without timestamps,
                            see tools/import_transcripts_md.py) -> snippets link to the video start, t = null
Lines starting with "#" are comments. Snippets are ASR text and are always labelled as such - never as quotes."""
from __future__ import annotations
import csv
import os
import re
import threading
from pathlib import Path

DISCLAIMER = ("Auto-transcribed speech (ASR, faster-whisper small or large-v3) - may contain errors, especially English finance "
              "terms. Paraphrase-level context only; not a verbatim quote and not investment advice.")
LINE = re.compile(r"^\[(\d+)\]\s*(.*)$")


def load_videos(path: Path) -> dict:
    vids = {}
    if path.exists():
        with open(path, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                vids[r["id"]] = {"id": r["id"], "date": r["date"], "title": r["title"]}
    return vids


class TranscriptIndex:
    def __init__(self, tdir: Path, videos: dict, indicators: dict):
        self.tdir, self.videos, self.indicators = Path(tdir), videos, indicators
        self.chunks: dict[str, list] = {}     # video_id -> [(pos, text, start_sec | None)]
        self._sig: dict[str, float] = {}
        self._cache: dict = {}
        self._lock = threading.RLock()
        self._rx = {k: [re.compile(p, re.I) for p in v.get("keywords", [])] for k, v in indicators.items()}

    # ---- indexing -------------------------------------------------
    @staticmethod
    def _chunk(text: str, win: int = 3, step: int = 2):
        """Returns [(pos, text, t)]: pos orders/de-duplicates windows, t is seconds (timed) or None (untimed)."""
        timed, untimed = [], []
        for ln in text.splitlines():
            ln = ln.strip()
            if not ln or ln.startswith("#"):
                continue
            m = LINE.match(ln)
            if m:
                if m.group(2).strip():
                    timed.append((int(m.group(1)), m.group(2).strip()))
            else:
                untimed.append(ln)
        out = []
        if timed:
            for i in range(0, len(timed), step):
                part = timed[i:i + win]
                out.append((part[0][0], " ".join(t for _, t in part)[:360], part[0][0]))
        else:
            # untimed: windows get a synthetic position 20 apart, so neighbouring (overlapping) windows are
            # skipped by the 25-unit overlap rule in search() just like overlapping timed windows.
            for n, i in enumerate(range(0, len(untimed), step)):
                out.append((n * 20, " ".join(untimed[i:i + win])[:360], None))
        return out

    def scan(self) -> dict:
        """Re-read new/changed files. Returns status."""
        with self._lock:
            changed = False
            present = set()
            if self.tdir.exists():
                for p in self.tdir.glob("*.txt"):
                    vid = p.stem
                    present.add(vid)
                    try:
                        mt = p.stat().st_mtime
                        if self._sig.get(vid) != mt:
                            if p.stat().st_size == 0:
                                continue
                            self.chunks[vid] = self._chunk(p.read_text(encoding="utf-8", errors="replace"))
                            self._sig[vid] = mt
                            changed = True
                    except OSError:
                        continue
            for vid in list(self.chunks):
                if vid not in present:
                    del self.chunks[vid]
                    self._sig.pop(vid, None)
                    changed = True
            if changed:
                self._cache.clear()
            return self.status()

    def status(self) -> dict:
        have = sorted(self.chunks)
        total = len(self.videos) or max(len(have), 90)
        return {"transcribed": len(have), "total": total, "missing": [v for v in self.videos if v not in self.chunks],
                "have": have, "disclaimer": DISCLAIMER}

    # ---- search ---------------------------------------------------
    def search(self, key: str, limit: int = 6, per_episode: int = 2) -> list:
        with self._lock:
            ck = (key, limit, per_episode)
            if ck in self._cache:
                return self._cache[ck]
            ind = self.indicators.get(key)
            if not ind:
                return []
            rxs = self._rx[key]
            need = int(ind.get("min_hits", 1))
            hits = []
            for vid, chunks in self.chunks.items():
                meta = self.videos.get(vid, {"id": vid, "date": "", "title": vid})
                scored = []
                for pos, text, t in chunks:
                    n = sum(1 for rx in rxs if rx.search(text))
                    if n >= need:
                        scored.append((n, pos, text, t))
                scored.sort(key=lambda x: (-x[0], x[1]))
                picked = []
                for n, pos, text, t in scored:
                    if len(picked) >= per_episode:
                        break
                    if any(abs(pos - p[1]) < 25 for p in picked):   # skip overlapping windows
                        continue
                    picked.append((n, pos, text, t))
                for n, pos, text, t in picked:
                    url = f"https://youtu.be/{vid}" + (f"?t={t}" if t is not None else "")
                    hits.append({"video_id": vid, "date": meta["date"], "title": meta["title"], "t": t, "hits": n,
                                 "text": text, "url": url, "basis": "own ASR", "timed": t is not None})
            hits.sort(key=lambda h: (h["date"], h["hits"]), reverse=True)   # recency first
            res = hits[:limit]
            self._cache[ck] = res
            return res

    def coverage(self, key: str) -> int:
        return len({h["video_id"] for h in self.search(key, limit=10_000, per_episode=1)})
