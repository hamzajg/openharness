from openharness.skill import Skill, skill


def test_skill_basic():
    @skill
    def greet(name: str, times: int = 1) -> str:
        """Say hello.

        This greets the given name N times.
        """
        return f"Hello {name}! " * times

    assert isinstance(greet, Skill)
    assert greet.name == "greet"
    assert greet.params == {"name": "str", "times": "int"}
    assert greet.non_deterministic is False
    assert "Say hello." in greet.description


def test_skill_invoke_converts_types():
    @skill
    def add(a: int, b: int) -> int:
        return a + b

    assert add.invoke(a="3", b="5") == 8
    assert add.invoke(a=3, b=5) == 8


def test_skill_non_deterministic_flag():
    @skill
    def sample() -> str:
        """Pick a random item. non_deterministic."""
        return "x"

    assert sample.non_deterministic is True


def test_skill_invoke_bool():
    @skill
    def flip(enabled: bool) -> str:
        return "on" if enabled else "off"

    assert flip.invoke(enabled="true") == "on"
    assert flip.invoke(enabled="false") == "off"
    assert flip.invoke(enabled=True) == "on"
