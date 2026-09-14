from openharness.frontmatter import parse


def test_no_frontmatter_returns_empty():
    assert parse("no frontmatter here\n") == {}
    assert parse("") == {}
    assert parse("--- not a real delimiter") == {}


def test_simple_key_values():
    text = """---
product: my-product
version: 0.1.0
count: 42
---
body here
"""
    out = parse(text)
    assert out["product"] == "my-product"
    assert out["version"] == "0.1.0"
    assert out["count"] == 42


def test_lists_and_empty_lists():
    text = """---
languages: [python, typescript, go]
frameworks: []
quoted: "hello world"
---
"""
    out = parse(text)
    assert out["languages"] == ["python", "typescript", "go"]
    assert out["frameworks"] == []
    assert out["quoted"] == "hello world"


def test_comments_and_blanks_ignored():
    text = """---
# ignored
a: 1

b: 2
---
"""
    out = parse(text)
    assert out == {"a": 1, "b": 2}


def test_no_end_delimiter():
    assert parse("---\na:1\n") == {}
