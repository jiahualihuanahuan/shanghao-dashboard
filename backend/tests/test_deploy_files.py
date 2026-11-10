from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def test_compose_structure():
    c = yaml.safe_load((ROOT / "docker-compose.yml").read_text())
    assert set(c["services"]) == {"backend", "web"}
    vols = c["services"]["backend"]["volumes"]
    assert any(v.endswith("/data/transcripts:ro") for v in vols), "transcripts must be mounted read-only"
    assert any(v.startswith("./config:") for v in vols)
    assert c["services"]["web"]["ports"][0].startswith("${BIND_ADDR:-127.0.0.1}")
    assert "FRED_API_KEY" in str(c["services"]["backend"]["environment"])


def test_env_example_has_no_secrets_and_gitignore():
    env = (ROOT / ".env.example").read_text()
    assert "FRED_API_KEY=" in env
    assert not [l for l in env.splitlines() if l.startswith("FRED_API_KEY=") and len(l.split("=", 1)[1].strip()) > 0]
    gi = (ROOT / ".gitignore").read_text()
    for pat in (".env", "*.sqlite", "transcripts/", "audio/", "node_modules/"):
        assert pat in gi
    assert not (ROOT / "LICENSE").exists() and not list(ROOT.glob("LICENSE*"))


def test_dockerfiles_exist():
    assert "uvicorn" in (ROOT / "backend" / "Dockerfile").read_text()
    assert "nginx" in (ROOT / "frontend" / "Dockerfile").read_text()
    assert "proxy_pass" in (ROOT / "frontend" / "nginx.conf").read_text()
