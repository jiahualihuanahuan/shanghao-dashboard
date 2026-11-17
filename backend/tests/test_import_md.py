import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("import_md", ROOT / "tools" / "import_transcripts_md.py")
imp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(imp)

from app.transcripts import TranscriptIndex, load_videos   # noqa: E402

CSV = "id,date,title,duration_s\nAAA,2024-11-05,2024年 11月5日,1\nBBB,2026-05-05,市场概述2026年4月21日,1\nCCC,2026-04-21,市场概述2026年4月21日,1\nDDD,2025-03-04,2025年4月3日,1\n"


def test_title_dates():
    assert imp.title_date("2024年 11月5日") == "2024-11-05"
    assert imp.title_date("市场概述  2025年3月18日") == "2025-03-18"
    assert imp.title_date("2024年6月4日一周市场展望") == "2024-06-04"
    assert imp.title_date("全球资本市场分析2月25日") == "????-02-25"
    assert imp.title_date("AI投资复盘") is None


def test_import_matches_titles_resolves_duplicates_and_keeps_existing(tmp_path, capsys):
    (tmp_path / "videos.csv").write_text(CSV, encoding="utf-8")
    out = tmp_path / "t"
    out.mkdir()
    (out / "BBB.txt").write_text("[0] 我今天早点开始 然后昨天有些新闻 海峡又开始互相放导弹 仓位方面\n", encoding="utf-8")
    (out / "CCC.txt").write_text("[0] OK 我讲几个事情 伊朗一会儿想谈 一会儿不想谈\n", encoding="utf-8")
    md = tmp_path / "all.md"
    md.write_text("## 2024年 11月5日\n十年期利率 很高, 长端 利率 上升 我觉得 降息 25个点\n\n"
                  "## 市场概述2026年4月21日\n我今天早点开始,然后昨天有些新闻, 海峡又开始互相放导弹, 仓位方面\n\n"
                  "## 不存在的标题\n文字\n", encoding="utf-8")
    assert imp.main([str(md), "--out", str(out), "--videos", str(tmp_path / "videos.csv")]) == 0
    s = json.loads(capsys.readouterr().out)
    assert [w["id"] for w in s["written"]] == ["AAA"]
    assert s["skipped_existing"] == [{"id": "BBB", "timed": True}]     # duplicate title resolved to BBB by overlap
    assert s["unmatched"][0]["title"] == "不存在的标题" and s["ambiguous"] == []
    assert {v["id"] for v in s["videos_without_section"]} == {"CCC", "DDD"}
    txt = (out / "AAA.txt").read_text(encoding="utf-8")
    assert txt.startswith("# AAA | 2024-11-05") and "[" not in txt.splitlines()[1]
    # --replace overwrites, --assign forces the duplicate
    imp.main([str(md), "--out", str(out), "--videos", str(tmp_path / "videos.csv"), "--replace",
              "--assign", "市场概述2026年4月21日=CCC"])
    s = json.loads(capsys.readouterr().out)
    assert {w["id"] for w in s["written"]} == {"AAA", "CCC"}
    ind = {"rates": {"title": "r", "topic": "T1", "min_hits": 1, "keywords": ["十年期"]}}
    ti = TranscriptIndex(out, load_videos(tmp_path / "videos.csv"), ind)
    ti.scan()
    h = ti.search("rates")
    assert h and h[0]["video_id"] == "AAA" and h[0]["t"] is None
