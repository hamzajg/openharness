import json, re, shutil as _sh
from pathlib import Path

_M = {"pyproject.toml":"python","setup.py":"python","requirements.txt":"python","package.json":"node","go.mod":"go","Cargo.toml":"rust","pom.xml":"java-maven","docker-compose.yml":"docker","Dockerfile":"docker"}
_T = ["python","node","npm","poetry","pnpm","docker","kubectl","terraform","git"]
_FW = {k:[k] for k in ("react","vue","next","express","django","flask","fastapi")}


def probe(root=None) -> dict:
    rt = Path(root or Path.cwd())
    r = {"languages":[],"frameworks":[],"tools":{},"ci":[],"infra":[]}
    seen = {ln for m,ln in _M.items() if (rt/m).exists()}
    if (rt/".github"/"workflows").exists(): r["ci"].append("github-actions")
    if (rt/"Dockerfile").exists() or (rt/"docker-compose.yml").exists(): r["infra"].append("docker")
    for t in _T:
        p = _sh.which(t)
        if p: r["tools"][t] = p
    pkg = rt/"package.json"
    if pkg.exists():
        try:
            d = json.loads(pkg.read_text())
            dps = dict(d.get("dependencies",{}) or {})
            dps.update(d.get("devDependencies",{}) or {})
            r["frameworks"] += [fw for fw,ks in _FW.items() if any(k in x.lower() for x in dps for k in ks)]
        except Exception: pass
    pp = rt/"pyproject.toml"
    if pp.exists():
        tx = pp.read_text()
        r["frameworks"] += [fw for fw,ks in _FW.items() if any(re.search(rf"\b{k}\b",tx,re.I) for k in ks)]
    r["languages"] = [ln for ln in seen if ln != "docker"]
    r["frameworks"] = list(dict.fromkeys(r["frameworks"]))
    return r


def drift(env_path=None) -> str:
    from .frontmatter import parse
    ep = Path(env_path or (Path.cwd()/".openharness"/"ENV.md"))
    dec = parse(ep.read_text()) if ep.exists() else {}
    live = probe(ep.parent.parent if ep.exists() else Path.cwd())
    _L = lambda x: [] if x in (None,"","[]") else ([x] if isinstance(x,str) else list(x))
    iss = [f"Undeclared framework: {fw}" for fw in live["frameworks"] if fw not in _L(dec.get("frameworks"))]
    iss += [f"Undeclared language: {ln}" for ln in live["languages"] if ln not in _L(dec.get("languages"))]
    return "env matches probed environment." if not iss else "\n".join(iss)
