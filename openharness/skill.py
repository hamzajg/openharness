from dataclasses import dataclass, field
from typing import Callable, get_type_hints
import inspect


@dataclass
class Skill:
    name: str
    description: str
    func: Callable
    params: dict = field(default_factory=dict)
    non_deterministic: bool = False

    def invoke(self, **kw):
        c = {}
        for p, t in self.params.items():
            if p not in kw: continue
            v = kw[p]
            if isinstance(v, str): v = int(v) if t=="int" else (v.lower() in ("true","1","yes") if t=="bool" else v)
            c[p] = v
        return self.func(**c)


def skill(f: Callable) -> Skill:
    doc = inspect.getdoc(f) or f.__name__
    h = get_type_hints(f)
    params = {p: (h[p].__name__ if h.get(p) and hasattr(h[p],"__name__") else "str") for p in inspect.signature(f).parameters}
    return Skill(f.__name__, doc, f, params, "non_deterministic" in doc.lower())
