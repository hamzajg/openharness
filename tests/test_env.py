import json
import os
from pathlib import Path

from openharness.env import probe, drift


def test_probe_detects_markers(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'x'\ndependencies = ['fastapi', 'django']\n")
    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    (tmp_path / ".github" / "workflows" / "ci.yml").write_text("name: ci")
    (tmp_path / "Dockerfile").write_text("FROM scratch")

    info = probe(tmp_path)
    assert "python" in info["languages"]
    assert "docker" in info["infra"]
    assert "github-actions" in info["ci"]
    assert "fastapi" in info["frameworks"]
    assert "django" in info["frameworks"]


def test_probe_detects_node_frameworks(tmp_path):
    (tmp_path / "package.json").write_text(json.dumps({
        "name": "x",
        "dependencies": {"react": "18.0.0", "express": "4.0.0", "next": "14.0.0"},
        "devDependencies": {"vue": "3.0.0"},
    }))
    info = probe(tmp_path)
    assert "node" in info["languages"]
    for fw in ("react", "express", "next", "vue"):
        assert fw in info["frameworks"]


def test_drift_reports_undeclared(tmp_path):
    (tmp_path / ".openharness").mkdir()
    env = tmp_path / ".openharness" / "ENV.md"
    env.write_text("""---
product: test
stage: greenfield
languages: []
frameworks: []
infra: []
ci: unset
---
""")
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'y'\ndependencies = ['flask']\n")
    cwd = Path.cwd()
    os.chdir(tmp_path)
    try:
        report = drift(env)
        assert "Undeclared framework: flask" in report
        assert "Undeclared language: python" in report
    finally:
        os.chdir(cwd)


def test_drift_matches_clean(tmp_path):
    (tmp_path / ".openharness").mkdir()
    env = tmp_path / ".openharness" / "ENV.md"
    (tmp_path / "pyproject.toml").write_text("name='z'")
    env.write_text("""---
product: clean
stage: greenfield
languages: [python]
frameworks: []
infra: []
ci: unset
---
""")
    cwd = Path.cwd()
    os.chdir(tmp_path)
    try:
        assert "env matches probed environment." == drift(env)
    finally:
        os.chdir(cwd)
