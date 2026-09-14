import json
import sys
from pathlib import Path


def main():
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
                kw[k] = vv if _ else "true"
        try:
            r = sk.invoke(**kw)
            print(r if r is not None else "")
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
    print("Verbs: run, ask, ingest, env, pull, self, serve", file=sys.stderr); sys.exit(1)


if __name__ == "__main__":
    main()
