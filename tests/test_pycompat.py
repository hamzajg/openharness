"""The CLI must explain an old interpreter instead of crashing on import.

Every module-level `X | Y` annotation raises TypeError below Python 3.10, and
the package declares `requires-python >= 3.13`, so `python3 -m openharness` on
3.9 used to die with a traceback from `openharness/registry.py`. The guard runs
before any project module is imported.
"""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from openharness.__main__ import MIN_PYTHON, main, python_version_error

ROOT = Path(__file__).resolve().parent.parent


def test_supported_interpreter_has_no_error():
    assert python_version_error((3, 13, 0)) is None
    assert python_version_error(tuple(sys.version_info)) is None


@pytest.mark.parametrize("old", [(3, 9, 6), (3, 7, 17), (2, 7, 18)])
def test_old_interpreter_message_is_actionable(old):
    message = python_version_error(old)

    assert message is not None
    assert f"requires Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]}+" in message
    assert ".".join(str(x) for x in old) in message
    # The point of the message is telling the user what to run instead.
    assert f"python{MIN_PYTHON[0]}.{MIN_PYTHON[1]}" in message


def test_main_exits_2_on_an_old_interpreter(monkeypatch, capsys):
    monkeypatch.setattr(sys, "version_info", (3, 9, 6))

    with pytest.raises(SystemExit) as exited:
        main()

    assert exited.value.code == 2
    err = capsys.readouterr().err
    assert "requires Python 3.13+" in err
    assert "3.9.6" in err
    assert "Traceback" not in err


def test_cli_lists_skills_on_the_current_interpreter():
    run = subprocess.run(
        [sys.executable, "-m", "openharness"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )

    assert run.returncode == 0, run.stderr
    assert "ship_loop" in run.stdout
    assert "wave_plan" in run.stdout


def _older_interpreter():
    """An interpreter below MIN_PYTHON on PATH, if this machine has one."""
    for candidate in ("python3.9", "python3.10", "python3.11", "python3.12", "python3"):
        exe = shutil.which(candidate)
        if not exe:
            continue
        version = subprocess.run(
            [exe, "-c", "import sys; print(sys.version_info[0], sys.version_info[1])"],
            capture_output=True,
            text=True,
        )
        if version.returncode != 0:
            continue
        major, minor = (int(part) for part in version.stdout.split())
        if (major, minor) < MIN_PYTHON:
            return exe
    return None


def test_real_old_interpreter_gets_the_message_not_a_traceback():
    exe = _older_interpreter()
    if not exe:
        pytest.skip(f"no interpreter older than {MIN_PYTHON[0]}.{MIN_PYTHON[1]} on PATH")

    run = subprocess.run([exe, "-m", "openharness"], cwd=ROOT, capture_output=True, text=True)

    assert run.returncode == 2, run.stdout + run.stderr
    assert "requires Python" in run.stderr
    assert "Traceback" not in run.stderr
    assert "unsupported operand type(s) for |" not in run.stderr
