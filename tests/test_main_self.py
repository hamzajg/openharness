"""`oh self` resolves SELF docs by name regardless of on-disk casing."""

import sys

import pytest

from openharness.__main__ import main


def _run(monkeypatch, capsys, *args):
    monkeypatch.setattr(sys, "argv", ["oh", "self", *args])
    main()
    return capsys.readouterr().out


def test_self_manifest_by_lowercase_name(monkeypatch, capsys):
    assert "OpenHarness MANIFEST" in _run(monkeypatch, capsys, "manifest")


def test_self_rules_doc_resolves_by_lowercase_name(monkeypatch, capsys):
    out = _run(monkeypatch, capsys, "evolution")
    assert "Rules for Agents Modifying the Harness" in out
    assert "D001–D019" in out


def test_unknown_self_doc_exits(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["oh", "self", "nope"])
    with pytest.raises(SystemExit):
        main()
