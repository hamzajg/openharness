import json
import sys
from pathlib import Path

#: Oldest interpreter this package runs on (pyproject: requires-python >= 3.13).
#: Below this, module-level `X | Y` annotations raise TypeError on import, so
#: the check must run before any project module is imported.
MIN_PYTHON = (3, 13)


def python_version_error(version_info=None):
    """Actionable message when the running interpreter is too old, else None."""
    v = sys.version_info if version_info is None else version_info
    if tuple(v[:2]) >= MIN_PYTHON:
        return None
    found = ".".join(str(x) for x in tuple(v)[:3])
    needed = f"{MIN_PYTHON[0]}.{MIN_PYTHON[1]}"
    return (
        f"openharness requires Python {needed}+ (pyproject: "
        f'requires-python = ">={needed}"), but this is Python {found}. '
        f"Re-run with a newer interpreter, e.g. `python{needed} -m openharness ...`."
    )


def main():
    unsupported = python_version_error()
    if unsupported:
        print(unsupported, file=sys.stderr)
        sys.exit(2)
    a = sys.argv[1:]
    if not a:
        from . import registry
        for s in sorted(registry.all_skills(), key=lambda x: x.name):
            f = s.description.splitlines()[0] if s.description else s.name
            print(f"{s.name:30s} {f}")
        return
    v, rest = a[0], a[1:]
    if v == "run":
        from . import registry
        if not rest:
            print("Usage: run <skill> --param=value ...", file=sys.stderr); sys.exit(1)
        sk = registry.get(rest[0])
        if not sk:
            print(f"Unknown skill: {rest[0]}", file=sys.stderr); sys.exit(1)
        kw = {}
        for x in rest[1:]:
            if x.startswith("--"):
                k, _, vv = x[2:].partition("=")
                kw[k.replace("-", "_")] = vv if _ else "true"
        from .skill import SkillError
        try:
            r = sk.invoke(**kw)
            print(r if r is not None else "")
        except SkillError as ex:
            print(f"{sk.name}: {ex}", file=sys.stderr)
            sys.exit(2)
        except TypeError as ex:
            print(f"Error: {ex}", file=sys.stderr); print(f"Params: {sk.params}", file=sys.stderr); sys.exit(1)
        return
    if v == "ask":
        from .knowledge import rag
        for c in rag.search(" ".join(rest)):
            print(c); print("---")
        return
    if v == "ingest":
        from .knowledge import rag
        p = Path(rest[0] if rest else ".")
        if p.is_dir():
            for md in p.rglob("*.md"):
                rag.ingest(path=str(md), text=md.read_text(), metadata={"source": str(md)})
        elif p.is_file():
            rag.ingest(path=str(p), text=p.read_text(), metadata={"source": str(p)})
        return
    if v == "env":
        from . import env as E
        from .frontmatter import parse
        rt = Path(rest[0]) if rest else Path.cwd()
        ep = rt / ".openharness" / "ENV.md"
        print(json.dumps({"probe": E.probe(rt), "env_declared": parse(ep.read_text()) if ep.exists() else {}, "drift": E.drift(ep)}, indent=2, default=str))
        return
    if v == "pull":
        from . import repos; repos.sync(*rest); return
    if v == "status":
        from . import repos
        st = repos.status(*rest)
        for name, info in sorted(st.items()):
            if not info.get("exists"):
                print(f"{name:30s} not cloned")
                continue
            br = info.get("branch", "?")
            def_br = info.get("default_branch", "?")
            dirty = " [DIRTY]" if info.get("dirty") else ""
            diverge = ""
            if info.get("ahead", 0) > 0 or info.get("behind", 0) > 0:
                diverge = f" (+{info.get('ahead', 0)}/-{info.get('behind', 0)})"
            mismatch = f" (expected {def_br})" if def_br and br != def_br else ""
            print(f"{name:30s} {br}{mismatch}{diverge}{dirty}")
        return
    if v == "prune":
        from . import repos
        remote = "--remote" in rest
        names = [x for x in rest if not x.startswith("--")]
        res = repos.prune(*names, remote=remote)
        for name, rec in sorted(res.items()):
            if rec["skipped"]:
                print(f"{name:30s} {rec['skipped']}")
                continue
            parts = []
            if rec["local"]:
                parts.append(f"local -{len(rec['local'])}: {', '.join(rec['local'])}")
            if rec["remote"]:
                parts.append(f"remote -{len(rec['remote'])}: {', '.join(rec['remote'])}")
            print(f"{name:30s} {'; '.join(parts) if parts else 'nothing to prune'}")
        return
    if v == "self":
        sr = Path(__file__).resolve().parent.parent / "SELF"
        if rest:
            p = sr / "blocks" / f"{rest[0]}.md"
            p = p if p.exists() else sr / f"{rest[0]}.md"
            if not p.exists():
                print(f"No such self doc: {rest[0]}", file=sys.stderr); sys.exit(1)
        else:
            p = sr / "MANIFEST.md"
        print(p.read_text()); return
    if v == "serve":
        host, port, i = "127.0.0.1", 7337, 0
        while i < len(rest):
            x = rest[i]
            if x == "--host" and i+1 < len(rest): host = rest[i+1]; i += 2
            elif x.startswith("--host="): host = x.split("=",1)[1]; i += 1
            elif x == "--port" and i+1 < len(rest): port = int(rest[i+1]); i += 2
            elif x.startswith("--port="): port = int(x.split("=",1)[1]); i += 1
            else: i += 1
        import uvicorn
        uvicorn.run("openharness.serve:app", host=host, port=port); return
    print(f"Unknown verb: {v}", file=sys.stderr)
    print("Verbs: run, ask, ingest, env, pull, status, prune, self, serve", file=sys.stderr); sys.exit(1)


if __name__ == "__main__":
    main()
