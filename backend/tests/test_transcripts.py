import time
from pathlib import Path

from app.transcripts import TranscriptIndex, load_videos

ROOT = Path(__file__).resolve().parents[2]
IND = {"rates": {"title": "Rates", "topic": "T1", "min_hits": 1, "keywords": ["十年期", r"\blong.?end\b"]},
       "strict": {"title": "Strict", "topic": "T1", "min_hits": 2, "keywords": ["十年期", "利率"]}}
VID = {"aaa": {"id": "aaa", "date": "2026-01-01", "title": "old"}, "bbb": {"id": "bbb", "date": "2026-06-01", "title": "new"},
       "ccc": {"id": "ccc", "date": "2026-09-01", "title": "newest"}}


def write(d, vid, lines):
    (d / f"{vid}.txt").write_text("\n".join(f"[{s}] {t}" for s, t in lines), encoding="utf-8")


def test_recency_first_and_links(tmp_path):
    write(tmp_path, "aaa", [(5, "十年期利率上升")])
    write(tmp_path, "bbb", [(70, "long end 卖出"), (400, "十年期 很高")])
    ti = TranscriptIndex(tmp_path, VID, IND)
    st = ti.scan()
    assert st["transcribed"] == 2 and st["total"] == 3 and st["missing"] == ["ccc"]
    hits = ti.search("rates", limit=5)
    assert [h["video_id"] for h in hits][0] == "bbb" and hits[-1]["video_id"] == "aaa"
    assert hits[0]["url"].startswith("https://youtu.be/bbb?t=") and hits[0]["basis"] == "own ASR"


def test_hot_reload_picks_up_new_files(tmp_path):
    write(tmp_path, "aaa", [(1, "十年期")])
    ti = TranscriptIndex(tmp_path, VID, IND)
    ti.scan()
    assert ti.coverage("rates") == 1
    write(tmp_path, "ccc", [(9, "十年期 又来了")])
    ti.scan()
    assert ti.coverage("rates") == 2 and ti.search("rates")[0]["video_id"] == "ccc"
    assert ti.status()["transcribed"] == 2


def test_min_hits_and_per_episode_limit_and_overlap(tmp_path):
    lines = [(i * 10, "十年期 利率" if i % 2 == 0 else "无关") for i in range(20)]
    write(tmp_path, "bbb", lines)
    ti = TranscriptIndex(tmp_path, VID, IND)
    ti.scan()
    assert len(ti.search("strict", per_episode=2)) == 2
    secs = sorted(h["t"] for h in ti.search("strict", per_episode=5))
    assert all(b - a >= 25 for a, b in zip(secs, secs[1:]))


def test_empty_and_missing_dir(tmp_path):
    ti = TranscriptIndex(tmp_path / "nope", VID, IND)
    assert ti.scan()["transcribed"] == 0 and ti.search("rates") == [] and ti.search("zzz") == []
    (tmp_path / "aaa.txt").write_text("")
    ti2 = TranscriptIndex(tmp_path, VID, IND)
    assert ti2.scan()["transcribed"] == 0


def test_real_config_indicators_compile_and_videos_seed():
    import yaml
    ind = yaml.safe_load((ROOT / "config" / "indicators.yaml").read_text())
    vids = load_videos(ROOT / "config" / "videos.csv")
    assert len(vids) == 90 and vids["Vk43i8mBJlA"]["date"] == "2025-12-30"   # title says 2026年12月30日
    assert vids["eiD3P7mzSRU"]["date"] == "2025-03-04" and vids["PweaTXhs-aU"]["date"] == "2026-05-05"
    ti = TranscriptIndex(Path("/nonexistent"), vids, ind["indicators"])
    assert len(ti.indicators) >= 15
    for k, v in ind["indicators"].items():
        assert v["topic"] in ind["topics"], k
