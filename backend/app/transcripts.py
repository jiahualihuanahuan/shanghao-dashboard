"""Transcript index behind the "Shanghao view" panel.

Reads /data/transcripts/<video_id>.txt (lines like "[123] text", seconds from start), re-scans by mtime so files that
arrive while the app runs are picked up. Snippets are ASR text and are always labelled as such - never as quotes."""
from __future__ import annotations
import csv
import os
import re
import threading
from pathlib import Path

DISCLAIMER = ("Auto-transcribed speech (ASR, faster-whisper small) - may contain errors, especially English finance "
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
        self.chunks: dict[str, list] = {}     # video_id -> [(start_sec, text)]
        self._sig: dict[str, float] = {}
        self._cache: dict = {}
        self._lock = threading.RLock()
        self._rx = {k: [re.compile(p, re.I) for p in v.get("keywords", [])] for k, v in indicators.items()}

    # ---- indexing -------------------------------------------------
    @staticmethod
    def _chunk(text: str, win: int = 3, step: int = 2):
        lines = []
        for ln in text.splitlines():
            m = LINE.match(ln.strip())
            if m and m.group(2):
                lines.append((int(m.group(1)), m.group(2).strip()))
        out = []
        for i in range(0, len(lines), step):
            part = lines[i:i + win]
            out.append((part[0][0], " ".join(t for _, t in part)[:360]))
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
                for sec, text in chunks:
                    n = sum(1 for rx in rxs if rx.search(text))
                    if n >= need:
                        scored.append((n, sec, text))
                scored.sort(key=lambda x: (-x[0], x[1]))
                picked = []
                for n, sec, text in scored:
                    if len(picked) >= per_episode:
                        break
                    if any(abs(sec - p[1]) < 25 for p in picked):   # skip overlapping windows
                        continue
                    picked.append((n, sec, text))
                for n, sec, text in picked:
                    hits.append({"video_id": vid, "date": meta["date"], "title": meta["title"], "t": sec, "hits": n,
                                 "text": text, "url": f"https://youtu.be/{vid}?t={sec}", "basis": "own ASR"})
            hits.sort(key=lambda h: (h["date"], h["hits"]), reverse=True)   # recency first
            res = hits[:limit]
            self._cache[ck] = res
            return res

    def coverage(self, key: str) -> int:
        return len({h["video_id"] for h in self.search(key, limit=10_000, per_episode=1)})
