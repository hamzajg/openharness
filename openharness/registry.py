import importlib.util as _iu, sys
from pathlib import Path
from .skill import Skill

_ROOT = Path(__file__).resolve().parent.parent / "skills"
_CACHE: dict[str, Skill] | None = None


def discover(root: Path | None = None, skills_root: Path | None = None) -> dict[str, Skill]:
    global _CACHE
    root = root or skills_root
    if _CACHE is not None and root is None: return _CACHE
    r, out = root or _ROOT, {}
    if not r.exists(): return out
    for py in r.rglob("*.py"):
        if py.name.startswith("_"): continue
        mn = "oh_" + py.stem
        sp = _iu.spec_from_file_location(mn, py)
        if not sp or not sp.loader: continue
        m = _iu.module_from_spec(sp)
        sys.modules[mn] = m
        try: sp.loader.exec_module(m)
        except Exception: continue
        for o in vars(m).values():
            if isinstance(o, Skill): out[o.name] = o
    if root is None: _CACHE = out
    return out


def get(name: str) -> Skill | None: return discover().get(name)
def all_skills() -> list[Skill]: return list(discover().values())


def as_prompt() -> str:
    ls = ["# Skill Catalog\n"]
    for s in sorted(all_skills(), key=lambda x: x.name):
        f = s.description.splitlines()[0] if s.description else s.name
        ps = ", ".join(f"{k}={v}" for k,v in s.params.items()) or "(none)"
        ls.append(f"## {s.name}\n- Params: {ps}\n- {f}\n")
    return "\n".join(ls)
