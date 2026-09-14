import re, subprocess as _sp
from pathlib import Path

_ROW = re.compile(r"^\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*$")


def entries(path=None) -> dict:
    p = Path(path or (Path.cwd()/"REPOS.md"))
    out: dict = {}
    if not p.exists(): return out
    for ln in p.read_text().splitlines():
        m = _ROW.match(ln)
        if not m: continue
        n,u,b,s = (m.group(i).strip() for i in (1,2,3,4))
        if n in ("name","") or "---" in n or not u: continue
        out[n] = {"url":u,"branch":b,"stage":s}
    return out


def sync(*names, repos_path=None):
    all_e = entries(repos_path)
    targets = list(names) if names else list(all_e.keys())
    src = Path.cwd()/"sources"
    src.mkdir(exist_ok=True)
    G = lambda *a: _sp.run(list(a), capture_output=True, text=True, check=True)
    for n in targets:
        e = all_e.get(n)
        if not e: print(f"!! {n}: not found in REPOS.md"); continue
        d = src/n
        try:
            if d.exists():
                G("git","-C",str(d),"pull","--ff-only")
                print(f"✓ {n}: pulled ({e['branch']})")
            else:
                a = ["git","clone"] + (["-b",e["branch"]] if e.get("branch") else []) + [e["url"],str(d)]
                G(*a)
                print(f"✓ {n}: cloned {e['url']} -> sources/{n}")
        except _sp.CalledProcessError as ex:
            print(f"!! {n}: {(ex.stderr or ex.stdout or str(ex)).strip()}")
