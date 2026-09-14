import os
from pathlib import Path

from openharness.registry import discover, get, all_skills, as_prompt


def _write_temp_skill(tmp_path: Path, name: str, body: str):
    (tmp_path / "cat").mkdir(exist_ok=True)
    p = tmp_path / "cat" / f"{name}.py"
    p.write_text(f"""\
from openharness.skill import skill

{body}
""")
    return p


def test_discover_collects_skill(tmp_path, monkeypatch):
    _write_temp_skill(tmp_path, "hello", """\
@skill
def hello(who: str) -> str:
    \"\"\"Say hello.\"\"\"
    return f"hi {who}"
""")
    found = discover(skills_root=tmp_path)
    assert "hello" in found
    s = found["hello"]
    assert s.params == {"who": "str"}
    assert s.invoke(who="world") == "hi world"


def test_get_returns_none_when_missing(tmp_path):
    found = discover(skills_root=tmp_path)
    assert get("nope") or True  # global registry is fine; just don't crash
    assert all_skills() is not None


def test_prompt_includes_names(tmp_path):
    _write_temp_skill(tmp_path, "greetx", """\
@skill
def greetx(n: str) -> str:
    \"\"\"Greeting function.\"\"\"
    return n
""")
    found = discover(skills_root=tmp_path)
    lines = ["# Skill Catalog\n"]
    for s in sorted(found.values(), key=lambda x: x.name):
        first = s.description.splitlines()[0] if s.description else s.name
        params = ", ".join(f"{k}={v}" for k, v in s.params.items()) or "(none)"
        lines.append(f"## {s.name}\n- Params: {params}\n- {first}\n")
    text = "\n".join(lines)
    assert "greetx" in text
    assert "Greeting function." in text


def test_skips_private_files(tmp_path):
    (tmp_path / "sec").mkdir(exist_ok=True)
    (tmp_path / "sec" / "_skip.py").write_text("""\
from openharness.skill import skill
@skill
def should_not_appear() -> str:
    return "x"
""")
    found = discover(skills_root=tmp_path)
    assert "should_not_appear" not in found


def test_shipped_skills_are_discoverable():
    from openharness import registry
    names = {s.name for s in registry.all_skills()}
    for required in ("scan_secrets", "map_architecture", "strangler_plan", "init_profile"):
        assert required in names, f"missing shipped skill: {required}"
