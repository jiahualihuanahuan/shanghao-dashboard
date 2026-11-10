#!/usr/bin/env python3
"""Optional helper: turn audio files into the transcript format the dashboard indexes.

    pip install faster-whisper          # not needed by the app itself
    python3 tools/transcribe.py --out transcripts  audio/<video_id>.mp3 ...

Writes <out>/<video_id>.txt with lines "[<start seconds>] <text>". The file name (video id) must match config/videos.csv.
Requires ffmpeg on PATH. CPU int8 "small" model runs at roughly 10x real time on 8 cores."""
import argparse
import os
import subprocess

import numpy as np
from faster_whisper import WhisperModel


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="transcripts")
    ap.add_argument("--model", default="small")
    ap.add_argument("--language", default="zh")
    ap.add_argument("--prompt", default="以下是普通话的美股市场分析。")
    ap.add_argument("files", nargs="+")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    model = WhisperModel(a.model, device="cpu", compute_type="int8")
    for f in a.files:
        vid = os.path.basename(f).split(".")[0]
        dest = os.path.join(a.out, f"{vid}.txt")
        if os.path.exists(dest):
            continue
        raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", f, "-f", "f32le", "-ac", "1", "-ar", "16000", "-"],
                             capture_output=True, check=True).stdout
        audio = np.frombuffer(raw, dtype=np.float32)
        segs, _ = model.transcribe(audio, language=a.language, vad_filter=True, beam_size=1, initial_prompt=a.prompt)
        tmp = dest + ".part"
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write("\n".join(f"[{int(s.start)}] {s.text.strip()}" for s in segs))
        os.replace(tmp, dest)   # atomic: the app never sees half-written files
        print(vid, "done", flush=True)


if __name__ == "__main__":
    main()
