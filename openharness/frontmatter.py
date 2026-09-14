import re

_PAT = re.compile(r"^([A-Za-z0-9_]+)\s*:\s*(.*)$")

def parse(text: str) -> dict:
    if not text.startswith("---\n"): return {}
    e = text.find("\n---\n", 4)
    if e == -1: return {}
    out = {}
    for ln in text[4:e].splitlines():
        if not ln or ln.lstrip().startswith("#"): continue
        m = _PAT.match(ln)
        if not m: continue
        k, v = m.group(1), m.group(2).strip()
        if v.startswith("[") and v.endswith("]"):
            i = v[1:-1].strip()
            out[k] = [s.strip().strip("\"'") for s in i.split(",")] if i else []
        elif v[:1] in "\"'" and v[-1:] == v[:1]: out[k] = v[1:-1]
        elif v == "": out[k] = ""
        else:
            try: out[k] = int(v) if "." not in v else float(v)
            except ValueError: out[k] = v
    return out
