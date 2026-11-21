"""`/init` writes the environment-specific registry, not the shipped template."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_init_profile_writes_local_registry(tmp_path):
    run = subprocess.run(
        [sys.executable, "-m", "openharness", "run", "init_profile",
         "--product=Demo", "--repos=demo:file:///tmp/demo:main|greenfield",
         f"--output_dir={tmp_path}"],
        cwd=ROOT, capture_output=True, text=True,
    )
    assert run.returncode == 0, run.stderr

    local = tmp_path / ".openharness" / "REPOS.local.md"
    assert local.exists()
    assert "| demo " in local.read_text()
    assert str(local) in run.stdout
    # The agnostic template in the harness root is not rewritten.
    assert not (tmp_path / "REPOS.md").exists()
