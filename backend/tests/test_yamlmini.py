from pathlib import Path

import yaml

from app import yamlmini

ROOT = Path(__file__).resolve().parents[2]


def test_default_alerts_match_pyyaml():
    mine = yamlmini.load(str(ROOT / "config" / "alerts.yaml"))
    ref = yaml.safe_load((ROOT / "config" / "alerts.yaml").read_text())
    assert mine == ref


def test_manual_inputs_match_pyyaml():
    mine = yamlmini.load(str(ROOT / "config" / "manual_inputs.yaml"))
    ref = yaml.safe_load((ROOT / "config" / "manual_inputs.yaml").read_text())
    assert mine == ref


def test_scalars_and_comments():
    d = yamlmini.loads('a: 1\nb: 2.5  # c\nc: "x # y"\nd: true\ne:\nlst:\n  - id: q\n    v: [1, "a", 3.5]\n  - id: r\n')
    assert d["a"] == 1 and d["b"] == 2.5 and d["c"] == "x # y" and d["d"] is True and d["e"] == []
    assert d["lst"][0] == {"id": "q", "v": [1, "a", 3.5]} and d["lst"][1] == {"id": "r"}


def test_bad_input_raises():
    import pytest
    with pytest.raises(ValueError):
        yamlmini.loads("  - orphan: 1\n")
