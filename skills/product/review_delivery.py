"""Independent delivery audit: prove a spec and its delivery are grounded in the repo.

The loop already has a per-wave reviewer and a delivery verifier, but both
trust the artifacts they are given. This skill is the factual half of an
independent audit: it reads `specs/<feature>/` and checks, deterministically,

- artifact presence for the phase (`spec` or `delivery`);
- traceability integrity: acceptance criterion -> scenario -> wave -> backlog
  -> LOOP, with no dangling references;
- claim verification: backticked paths, scripts, endpoints, and ADRs named in
  the artifacts actually exist (the anti-hallucination core);
- evidence integrity: placeholder wave/gate evidence, missing `file:` gate
  artifacts, weak or empty validation rows, unresolved spec markers;
- scope drift (delivery): changed files outside the spec's in-scope paths;
- hallucination markers in changed product code.

It emits an audit brief with findings grouped by severity and a verdict block.
It does **not** judge semantics or emit a verdict: the `delivery-auditor`
subagent re-verifies each finding, reads the code, and fills the verdict.
Deterministic; stdlib only.
"""

import os
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from openharness import evidence as evidence_bundles
from openharness.skill import skill
from skills.product.spec_scaffold import value_contract_status

_SKIP_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build",
    "vendor", ".chroma", ".next", ".nuget", "bin", "obj", "target",
    ".gradle", "Pods", "coverage", "specs", "docs",
}
_CODE_EXTS = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".kt", ".cs", ".go", ".rs",
    ".rb", ".php", ".swift", ".m", ".scala", ".groovy",
}
_PATH_EXTS = _CODE_EXTS | {
    ".md", ".sql", ".json", ".yaml", ".yml", ".feature", ".sh", ".gradle",
    ".toml", ".xml", ".html", ".css", ".properties", ".lock",
}
_MAX_FILE = 256 * 1024
_MAX_FINDINGS = 120
_MAX_PER_CODE = 20

_SCENARIO_RE = re.compile(r"^\s*Scenario(?: Outline)?:\s*(.+?)\s*$")
_TAG_RE = re.compile(r"@w(\d+)")
_AC_RE = re.compile(r"^\|\s*(\d+)\s*\|\s*([^|]+?)\s*\|\s*([^|]*?)\s*\|\s*$")
_NUMBERED_AC_RE = re.compile(r"^\s*(\d+)[.)]\s+(.+?)\s*$")
_AC_SECTION_RE = re.compile(r"^##\s+Acceptance criteria\s*$", re.M | re.I)
_ITEM_RE = re.compile(r"^##\s+(B|US)(\d+)\s*[—-]\s*(.+)$", re.M)
_WAVE_RE = re.compile(r"^##\s+Wave\s+(\d+)\b.*$", re.M)
_GATE_RE = re.compile(r"^##\s+(G\d+)\s*[—-]\s*(.+)$", re.M)
_LOOP_WAVE_RE = re.compile(
    r"^\|\s*(\d+)\s*\|\s*([a-z-]+)\s*\|\s*([^|]*?)\s*\|\s*([^|]*?)\s*\|"
    r"\s*([^|]*?)\s*\|",
    re.M,
)
_LOOP_GATE_RE = re.compile(
    r"^\|\s*(G\d+)\s*\|\s*([a-z-]+)\s*\|\s*([^|]*?)\s*\|\s*([^|]*?)\s*\|",
    re.M,
)
_VALIDATION_ROW_RE = re.compile(
    r"^\|\s*(\d+)\s*\|\s*([^|]*?)\s*\|\s*([^|]*?)\s*\|\s*([^|]*?)\s*\|"
    r"\s*([^|]*?)\s*\|\s*$",
    re.M,
)
_ENDPOINT_RE = re.compile(
    r"\b(GET|POST|PUT|PATCH|DELETE)\s+(/[A-Za-z0-9_\-{}/.:]+)", re.I
)
_ROUTE_ATTR_RE = re.compile(
    r"@(?:Post|Get|Put|Patch|Delete)Mapping|"
    r"\[Http(?:Post|Get|Put|Patch|Delete)\]|"
    r"\.(?:post|get|put|patch|delete)\s*\(",
    re.I,
)
_ADR_RE = re.compile(r"\bADR[- ]?(\d{1,4})\b", re.I)
_SCRIPT_RE = re.compile(
    r"(?:^|\s)((?:\./)?(?:gradlew|scripts/[\w./-]+|[\w./-]+\.sh))(?:\s|$)"
)
_BUILD_CMD_RE = re.compile(
    r"\b(?:sh\s+\S+|npm\s+\w+|pnpm\s+\w+|yarn\s+\w+|pytest|gradlew|"
    r"mvn|dotnet\s+\w+|go\s+test|cargo\s+test|make\s+\w+)\b",
    re.I,
)
_FUTURE_RE = re.compile(
    r"\b(?:create|add|new|will|plan|planned|target|introduce|future|"
    r"not yet|to be)\b", re.I
)
_CURRENT_RE = re.compile(
    r"\b(?:already|currently|exists?|existing|today|now)\b", re.I
)
_NEGATED_RE = re.compile(
    r"\b(?:instead of|rather than|not|never|no longer|removed|dead|"
    r"deprecated|without|replac(?:e|ed|es)|drop(?:ped)?)\b",
    re.I,
)
_UNRESOLVED_RE = re.compile(
    r"\b(?:TBD|TODO|FIXME|XXX|\?\?\?|to be decided|to be determined)\b", re.I
)
_ASPIRATIONAL_RE = re.compile(
    r"\b(?:planned|TBD|coming soon|"
    r"not yet (?:validated|covered|tested)|"
    r"will be (?:validated|covered|tested|added)|"
    r"to be (?:validated|covered|tested))\b",
    re.I,
)
_GAP_NOISE_RE = re.compile(
    r"\b(?:out of scope|not applicable|heuristic artifact|not evidence|"
    r"disregarded|acceptable per spec)\b",
    re.I,
)
# Terminology vs product truth: user-facing copy must not promise
# capabilities the spec disclaims. Two complementary checks:
#  1. Generic — capability terms declared in SPEC.md "Scope (out)" /
#     "Non-goals" sections are matched (with simple plural tolerance)
#     against scenario/backlog wording and quoted/JSX text in changed
#     UI sources.
#  2. Auth phrases — "no auth"-style disclaimers additionally catch
#     multi-word auth wording ("sign in", "log in") that single-term
#     extraction cannot see.
# Both report a concern for the auditor, never a blocker.
_AUTH_DISCLAIMER_RE = re.compile(
    r"\b(?:no auth|no real auth|without auth|not authenticated|"
    r"unauthenticated|anonymous)\b",
    re.I,
)
_AUTH_CLAIM_RE = re.compile(
    r"\b(?:accounts?|log ?in|login|sign ?in|sign ?up|passwords?|"
    r"register(?:s|ed|ing|ation)?|credentials?|"
    r"authenticat\w*|authori[sz]ation)\b",
    re.I,
)
_SCOPE_SECTION_RE = re.compile(
    r"^##\s+(Scope\s*\(?(?:in|out)\)?|Non-goals?|Out of scope)\b"
    r"(.*?)(?=^##\s|\Z)",
    re.M | re.S | re.I,
)
_WORD_RE = re.compile(r"[A-Za-z]{5,}")
_CAPABILITY_STOPWORDS = {
    "about", "above", "across", "after", "again", "against", "along",
    "also", "among", "another", "anything", "application", "applications",
    "app", "apps", "around", "because", "become", "before", "being",
    "below", "between", "build", "called", "cannot", "change", "changes",
    "could", "domain", "domains", "doing", "done", "during", "each",
    "either", "every", "example", "examples", "except", "feature",
    "features", "first", "following", "front", "frontend", "future",
    "given", "going", "having", "implementation", "instead", "itself",
    "later", "least", "level", "like", "made", "make", "many", "might",
    "more", "most", "much", "must", "name", "never", "next", "nice",
    "nothing", "often", "once", "only", "other", "others", "over",
    "part", "parts", "pass", "passed", "per",
    "place", "please", "polish", "possible", "probably", "product",
    "real", "really", "reason", "refactor", "related", "remain",
    "requires", "right", "same", "scenario", "scenarios", "seem",
    "should", "since", "small", "some", "something", "sometimes",
    "still", "stuff", "such", "take", "than", "that", "their", "them",
    "then", "there", "these", "they", "thing", "things", "this", "those",
    "though", "through", "thus", "under", "until", "upon", "using",
    "usually", "very", "want", "wants", "wave", "waves", "well", "were",
    "what", "when", "where", "which", "while", "will", "with", "within",
    "without", "would", "your", "yours",
}
_OUT_OF_SCOPE_HEADING_RE = re.compile(
    r"out of scope|non-goal|excluded|future|won'?t have|deferred",
    re.I,
)
_COPY_EXTS = {".tsx", ".jsx", ".html", ".vue", ".svelte"}
_HEADING_RE = re.compile(r"^#{1,6}\s")
_HALLUCINATION_RE = re.compile(
    r"\b(?:TODO|FIXME|XXX|HACK|NOT\s+IMPLEMENTED|NOT\s+YET\s+IMPLEMENTED|"
    r"COMING\s+SOON)\b",
    re.I,
)
_QUOTED_RE = re.compile(
    r"'(?:\\.|[^'\\])*'|\"(?:\\.|[^\"\\])*\"|`(?:\\.|[^`\\])*`"
)
_PLACEHOLDER_EVIDENCE = re.compile(
    r"^(?:done|ok|okay|yes|no|n/?a|tbd|todo|pending|green|"
    r"all tests pass|tests pass|passed|complete|completed|"
    r"✓|—|-|\.)$",
    re.I,
)
_EVIDENCE_SIGNAL = re.compile(
    r"(?:#\d+|\b\d+/\d+\b|\b\d{5,}\b|\b[0-9a-f]{7,40}\b|https?://|"
    r"CI\b|\btests?\b|\bpytest\b|\bnpm\b|"
    r"\bgradlew\b|\bGET\b|\bPOST\b|\bPATCH\b|\bDELETE\b|`|/)",
    re.I,
)


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _read(path: Path) -> str:
    try:
        return path.read_text(errors="ignore")
    except OSError:
        return ""


def _rel(root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path)


def _display_path(path: Path) -> str:
    """Render a path for human-facing output, collapsing the user's home
    directory to `~` so absolute host paths never leak into committed
    audit files (security: see ADR 0004)."""
    try:
        home = Path.home()
        rel = path.resolve().relative_to(home)
        return f"~/{rel}"
    except (ValueError, OSError):
        return str(path)


@dataclass
class Finding:
    severity: str  # blocker | concern | unverified
    code: str
    where: str
    message: str


# ----------------------------------------------------------------- parsing

def _parse_scenarios(text: str) -> list[dict]:
    out, pending = [], []
    for i, line in enumerate(text.splitlines(), 1):
        s = line.strip()
        if s.startswith("@"):
            pending = [int(w) for w in _TAG_RE.findall(s)]
        elif _SCENARIO_RE.match(s):
            out.append({
                "name": _SCENARIO_RE.match(s).group(1),
                "waves": set(pending),
                "line": i,
            })
            pending = []
    return out


def _acceptance_block(text: str) -> tuple[str, int] | None:
    """Return (block, first_line_no) for `## Acceptance criteria`, if present."""
    m = _AC_SECTION_RE.search(text)
    if not m:
        return None
    rest = text[m.end():]
    nxt = re.search(r"^##\s+", rest, re.M)
    block = rest[:nxt.start()] if nxt else rest
    # m.end() is the end of the heading line; the block starts on the next line.
    return block, text[:m.end()].count("\n") + 2


def _parse_acs(text: str) -> list[dict]:
    has_section = _acceptance_block(text) is not None
    section = _acceptance_block(text) or (text, 1)
    block, first_line = section
    table_rows: list[dict] = []
    numbered_rows: list[dict] = []
    for offset, line in enumerate(block.splitlines()):
        line_no = first_line + offset
        m = _AC_RE.match(line)
        if m:
            criterion = m.group(2).strip()
            if criterion.lower() == "criterion" or set(criterion) <= {"-", ":"}:
                continue
            table_rows.append({
                "n": int(m.group(1)),
                "criterion": criterion,
                "refs": m.group(3).strip(),
                "line": line_no,
            })
            continue
        if not has_section:
            continue
        nm = _NUMBERED_AC_RE.match(line)
        if not nm or line.lstrip().startswith("|"):
            continue
        criterion = nm.group(2).strip()
        if not criterion or criterion.lower() in ("criterion", "acceptance criteria"):
            continue
        # Numbered items carry their scenario refs inline (`@w1`, a verbatim
        # scenario name, or both); the text itself is the reference cell.
        numbered_rows.append({
            "n": int(nm.group(1)),
            "criterion": criterion,
            "refs": criterion,
            "line": line_no,
        })
    return table_rows or numbered_rows


def _parse_backlog(text: str) -> list[dict]:
    out = []
    matches = list(_ITEM_RE.finditer(text))
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        block = text[m.end():end]
        scen = re.search(r"^-\s*Scenarios:\s*(.+)$", block, re.M)
        deps = re.search(r"^-\s*Depends:\s*(.+)$", block, re.M)
        out.append({
            "id": f"{m.group(1)}{m.group(2)}",
            "title": m.group(3).strip(),
            "waves": {int(w) for w in _TAG_RE.findall(scen.group(1))} if scen else set(),
            "deps": re.findall(r"(?:B|US)(\d+)", deps.group(1)) if deps else [],
            "line": text[:m.start()].count("\n") + 1,
        })
    return out


def _parse_waves(text: str) -> dict[int, dict]:
    out: dict[int, dict] = {}
    matches = list(_WAVE_RE.finditer(text))
    for i, m in enumerate(matches):
        n = int(m.group(1))
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        block = text[m.end():end]
        out[n] = {
            "items": re.findall(r"^\|\s*((?:US|B)\d+)\s*\|", block, re.M),
            "line": text[:m.start()].count("\n") + 1,
        }
    return out


def _parse_loop(text: str) -> dict:
    status_m = re.search(r"^Status:\s*(\S+)\s*$", text, re.M)
    waves = {}
    for m in _LOOP_WAVE_RE.finditer(text):
        waves[int(m.group(1))] = {
            "status": m.group(2),
            "branch": m.group(3).strip(),
            "pr": m.group(4).strip(),
            "evidence": m.group(5).strip(),
        }
    gates = {}
    for m in _LOOP_GATE_RE.finditer(text):
        gates[m.group(1).upper()] = {
            "status": m.group(2),
            "evidence": m.group(3).strip(),
        }
    return {
        "status": status_m.group(1) if status_m else "running",
        "waves": waves,
        "gates": gates,
    }


def _parse_gates(text: str) -> dict[str, dict]:
    out: dict[str, dict] = {}
    matches = list(_GATE_RE.finditer(text))
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        block = text[m.end():end]

        def field(name: str) -> str:
            fm = re.search(rf"^-\s*{re.escape(name)}:\s*(.*)$", block, re.M | re.I)
            return fm.group(1).strip() if fm else ""

        out[m.group(1).upper()] = {
            "title": m.group(2).strip(),
            "before": field("Before").lower(),
            "resolver": field("Resolver").lower(),
            "blocking": field("Blocking").lower() != "no",
            "check": field("Check"),
        }
    return out


_MANUAL_SECTION_RE = re.compile(r"^##\s+Manual verification\s*$", re.M | re.I)
_MANUAL_AC_RE = re.compile(r"^\s*-\s*AC\s*(\d+)\b\s*[—:–-]?\s*(.+?)\s*$")


def _parse_validation(text: str) -> list[dict]:
    rows = []
    for m in _VALIDATION_ROW_RE.finditer(text):
        criterion = m.group(2).strip()
        if criterion.lower() in ("criterion", "---") or set(criterion) <= {"-", ":"}:
            continue
        rows.append({
            "n": int(m.group(1)),
            "criterion": criterion,
            "scenarios": m.group(3).strip(),
            "waves": m.group(4).strip(),
            "evidence": m.group(5).strip(),
        })
    return rows


def _manual_acs(text: str) -> set[int]:
    """AC numbers with a substantive `## Manual verification` entry."""
    m = _MANUAL_SECTION_RE.search(text)
    if not m:
        return set()
    rest = text[m.end():]
    nxt = re.search(r"^##\s+", rest, re.M)
    block = rest[:nxt.start()] if nxt else rest
    out = set()
    for line in block.splitlines():
        am = _MANUAL_AC_RE.match(line)
        if am and len(am.group(2)) >= 10:
            out.add(int(am.group(1)))
    return out


# ------------------------------------------------------------ claim checks

def _path_tokens(text: str):
    """Yield (token, line number) for backticked tokens that look like paths."""
    for i, line in enumerate(text.splitlines(), 1):
        for token in re.findall(r"`([^`]+)`", line):
            yield token.strip(), i


def _looks_like_path(token: str) -> bool:
    if not token or " " in token:
        return False
    if re.match(r"^(?:https?://|mailto:)", token, re.I):
        return False
    if re.match(r"^[@#]", token) or re.match(r"^(?:G|US|B)\d+$", token, re.I):
        return False
    # `/identity/me`, `/api/v1/orders/create` — HTTP routes, not repo paths.
    if token.startswith("/"):
        return False
    # `VALID/INVALID/UNAVAILABLE` — an enum list, not a path.
    if re.match(r"^[A-Z][A-Z0-9_]*(?:/[A-Z][A-Z0-9_]*)+$", token):
        return False
    if any(c in token for c in "<>*{}[]"):
        return False
    # `org.json`, `com.google.gson` — package/group ids, not files.
    if "/" not in token and re.match(
        r"^(?:com|org|net|io|dev|edu|gov|co|androidx)\.[a-z0-9.]+$", token, re.I
    ):
        return False
    # `viaviweb.in/envato/...` — a URL without a scheme.
    first = token.split("/", 1)[0]
    if "/" in token and re.match(r"^[a-z0-9-]+\.[a-z]{2,}$", first, re.I):
        return False
    if token.endswith("/"):
        return True
    if "/" in token:
        return True
    return Path(token).suffix.lower() in _PATH_EXTS


def _suffix_match(root: Path, token: str) -> Path | None:
    """Resolve a source-root-relative path such as `assets/catalog.json`.

    Android/Java/monorepo specs often name a path relative to a source root
    (`app/src/main/assets`), not the repo root. A suffix match finds it without
    pretending the literal repo-root path exists.
    """
    needle = token.strip().lstrip("./").rstrip("/")
    if not needle:
        return None
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [
            d for d in dirnames
            if d not in _SKIP_DIRS and not d.startswith(".")
        ]
        rel = Path(dirpath).relative_to(root)
        if len(rel.parts) >= 12:
            dirnames[:] = []
        for name in dirnames + filenames:
            posix = (rel / name).as_posix()
            if posix == needle or posix.endswith("/" + needle):
                return Path(dirpath) / name
    return None


def _resolve(root: Path, spec_dir: Path, token: str) -> Path | None:
    p = Path(token)
    if p.is_absolute():
        return p if p.exists() else None
    for base in (root, spec_dir, spec_dir.parent):
        candidate = base / token
        if candidate.exists():
            return candidate
    return _suffix_match(root, token)


def _branch_like(token: str) -> bool:
    return bool(re.match(r"^(?:feat|fix|chore|docs|test|evolve)/[\w./-]+$", token))


def _command_scripts(text: str):
    """Yield (command, script path) for shell commands that name a repo script.

    Handles both a bare command line (`sh scripts/verify.sh`) and an inline
    backticked command in prose (`Verify with `sh scripts/verify.sh``).
    """
    for i, line in enumerate(text.splitlines(), 1):
        candidates = [line.strip()]
        candidates += [m.group(1).strip() for m in re.finditer(r"`([^`]+)`", line)]
        for candidate in candidates:
            s = candidate.strip().strip("`").strip()
            if s.startswith("sh "):
                s = s[3:].strip()
            for m in _SCRIPT_RE.finditer(s):
                script = m.group(1)
                if script.startswith("./"):
                    script = script[2:]
                if script.endswith(".sh") or script == "gradlew":
                    yield line.strip(), script, i


def _endpoints(text: str):
    for i, line in enumerate(text.splitlines(), 1):
        for m in _ENDPOINT_RE.finditer(line):
            # `GET /customers/by-email.` — the period ends the sentence, it is
            # not part of the route.
            path = m.group(2).rstrip(".,;:")
            if path and path != "/":
                yield m.group(1).upper(), path, i


def _source_files(root: Path):
    count = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames
                       if d not in _SKIP_DIRS and not d.startswith(".")]
        for name in filenames:
            p = Path(dirpath) / name
            if p.suffix.lower() not in _CODE_EXTS:
                continue
            low = name.lower()
            if "test" in low or "spec" in low:
                continue
            try:
                if p.stat().st_size > _MAX_FILE:
                    continue
            except OSError:
                continue
            yield p
            count += 1
            if count >= 600:
                return


def _endpoint_in_code(root: Path, method: str, path: str) -> bool:
    """True when the endpoint is declared literally or composed from annotations.

    Frameworks split a route across a class-level prefix and a method-level
    suffix (`@RequestMapping("/orders")` + `@PostMapping("/{id}/cancel")`), or
    derive it from a controller name (`[Route("[controller]")]` + `[HttpPost]`
    -> `/Products`). A literal search misses both; the heuristics below catch
    the composition without matching random prose.
    """
    needle = re.sub(r"\{[^}]+\}|:[A-Za-z_]\w*|<[^>]+>", "", path).rstrip("/")
    if len(needle) < 4:
        return True
    segments = [s for s in needle.split("/") if len(s) >= 3]
    low_needle = needle.lower()
    for f in _source_files(root):
        text = _read(f)
        low = text.lower()
        if low_needle in low:
            return True
        if len(segments) >= 2 and all(s.lower() in low for s in segments):
            return True
        if (
            len(segments) == 1
            and segments[0].lower() in low
            and _ROUTE_ATTR_RE.search(text)
        ):
            return True
    return False


def _adr_exists(root: Path, number: str) -> bool:
    adr_dir = root / "docs" / "adr"
    if not adr_dir.is_dir():
        return True
    n = number.lstrip("0") or "0"
    for p in adr_dir.glob("*.md"):
        if re.search(rf"\b0*{re.escape(n)}\b", p.name):
            return True
    return False


def _placeholder_evidence(text: str) -> bool:
    s = text.strip()
    if not s:
        return True
    if _PLACEHOLDER_EVIDENCE.match(s):
        return True
    return not bool(_EVIDENCE_SIGNAL.search(s))


def _dir_named(root: Path, name: str) -> Path | None:
    """Find a directory with this exact name (e.g. `Order.App` -> src/Order.App)."""
    for dirpath, dirnames, _ in os.walk(root):
        dirnames[:] = [
            d for d in dirnames
            if d not in _SKIP_DIRS and not d.startswith(".")
        ]
        rel = Path(dirpath).relative_to(root)
        if len(rel.parts) >= 4:
            dirnames[:] = []
        if name in dirnames:
            return Path(dirpath) / name
    return None


def _scope_paths(root: Path, spec_dir: Path, spec_text: str) -> list[str]:
    """Repo-relative paths the spec declares in scope.

    Only explicit evidence counts: a backticked path that exists or has a code
    extension, a backticked module name that maps to a directory, or a bare
    token that resolves on disk. A field list such as
    `productId/sku/name/qty` is not a path and must not become one.
    """
    m = re.search(r"^##\s+Scope\s*\(in\)\s*$", spec_text, re.M | re.I)
    if not m:
        return []
    rest = spec_text[m.end():]
    nxt = re.search(r"^##\s+", rest, re.M)
    block = rest[:nxt.start()] if nxt else rest
    paths = []
    for line in block.splitlines():
        for token in re.findall(r"`([^`]+)`", line):
            token = token.strip().rstrip("/")
            if not token or " " in token or token.startswith(("http://", "https://")):
                continue
            resolved = _resolve(root, spec_dir, token)
            if resolved is not None:
                paths.append(_rel(root, resolved))
            elif Path(token).suffix.lower() in _CODE_EXTS:
                paths.append(token)
            elif "/" not in token and not re.search(r"[(){}<>]", token):
                found = _dir_named(root, token)
                if found is not None:
                    paths.append(_rel(root, found))
        for token in re.findall(r"(?:^|\s)([\w.-]+/[\w./-]+)", line):
            resolved = _resolve(root, spec_dir, token)
            if resolved is not None:
                paths.append(_rel(root, resolved))
    return sorted(set(paths))


def _changed_files(root: Path, changed: str, base: str) -> tuple[list[str], str]:
    if changed.strip():
        return [x for x in re.split(r"[,\s]+", changed.strip()) if x], "explicit"
    bases = [base] if base else ["origin/main", "origin/master", "main", "master"]
    for ref in bases:
        try:
            proc = subprocess.run(
                ["git", "-C", str(root), "diff", "--name-only", f"{ref}...HEAD"],
                capture_output=True, text=True, timeout=20,
            )
        except (OSError, subprocess.SubprocessError):
            return [], "git unavailable"
        if proc.returncode == 0:
            return [x for x in proc.stdout.splitlines() if x.strip()], ref
    return [], "no git base ref"


def _in_scope(path: str, scope: list[str]) -> bool:
    for s in scope:
        if path == s or path.startswith(s + "/"):
            return True
    return False


def _is_test_path(path: str) -> bool:
    parts = [p.lower() for p in Path(path).parts[:-1]]
    if any(
        p in {"test", "tests", "__tests__", "testdata", "fixtures"}
        or p.endswith(".tests")
        for p in parts
    ):
        return True
    name = Path(path).name.lower()
    return (
        name.startswith("test_")
        or name.endswith(("_test.py", "test.cs", ".test.ts", ".test.tsx",
                          ".spec.ts", ".spec.tsx"))
    )


def _unfinished_marker(line: str) -> bool:
    """True for explicit unfinished markers outside string literals.

    Quoted values are blanked first so domain enums (`status: 'todo'`), HTML
    attributes (`placeholder="New name"`), and fixture strings do not read as
    unfinished implementation.
    """
    return bool(_HALLUCINATION_RE.search(_QUOTED_RE.sub('""', line)))


def _out_of_scope_exempt(path: str) -> bool:
    return (
        path.startswith(("specs/", "docs/", ".github/", "evidence/", ".openharness/evidence/"))
        or path in {"README.md", "AGENTS.md", "CHANGELOG.md"}
        or path.endswith((".lock", "package-lock.json", "yarn.lock", "poetry.lock"))
        or _is_test_path(path)
    )


# ------------------------------------------------------------------ audit

_PROSE_LINE_RE = re.compile(r"[A-Za-z][A-Za-z0-9 ,.'&!?:;\-—]{2,80}")
_CODEISH_RE = re.compile(r"[=;{}<>()\\/]")


def _copy_fragments(line: str) -> list[str]:
    """User-visible text on a source line: quoted strings, JSX text,
    and bare prose lines (JSX text often sits alone between tags)."""
    frags = [m.group(0) for m in _QUOTED_RE.finditer(line)]
    frags.extend(re.findall(r">([^<>{}]+)<", line))
    stripped = line.strip()
    if _PROSE_LINE_RE.fullmatch(stripped) and not _CODEISH_RE.search(stripped):
        frags.append(stripped)
    return frags


def _auth_claim_unnegated(text: str) -> bool:
    return bool(_AUTH_CLAIM_RE.search(text)) and not (
        _AUTH_DISCLAIMER_RE.search(text) or _NEGATED_RE.search(text)
    )


def _deplural(word: str) -> str:
    w = word.lower()
    if w.endswith("ies") and len(w) > 4:
        return w[:-3] + "y"
    if w.endswith("es") and len(w) > 4:
        return w[:-2]
    if w.endswith("s") and len(w) > 4:
        return w[:-1]
    return w


def _capability_terms(spec_text: str) -> set[str]:
    """Capability nouns declared out of scope, minus in-scope words.

    Terms come from SPEC.md `## Scope (out)` / `## Non-goals` /
    `## Out of scope` sections; anything also named under `## Scope (in)`
    (plural-tolerant) or matching a stopword is dropped to keep the
    signal precise.
    """
    in_text = out_text = ""
    for m in _SCOPE_SECTION_RE.finditer(spec_text):
        heading = m.group(1).strip().lower()
        is_out = "out" in heading or heading.startswith(
            ("non-goal", "out of scope")
        )
        if is_out:
            out_text += m.group(2)
        else:
            in_text += m.group(2)
    in_norms = {_deplural(w) for w in _WORD_RE.findall(in_text)}
    return {
        w.lower()
        for w in _WORD_RE.findall(out_text)
        if _deplural(w) not in in_norms
        and w.lower() not in _CAPABILITY_STOPWORDS
    }


def _capability_pattern(terms: set[str]) -> re.Pattern | None:
    if not terms:
        return None
    variants: set[str] = set()
    for t in terms:
        variants.add(t)
        variants.add(t[:-1] if t.endswith("s") else t + "s")
    body = "|".join(
        sorted((re.escape(v) for v in variants), key=len, reverse=True)
    )
    return re.compile(rf"\b(?:{body})\b", re.I)


def _capability_hit(pattern: re.Pattern, text: str) -> str | None:
    m = pattern.search(text)
    return m.group(0) if m else None


def _audit(root: Path, spec_dir: Path, phase: str, changed: str, base: str) -> tuple[str, list[Finding]]:
    findings: list[Finding] = []
    artifacts = {
        "SPEC.md": _read(spec_dir / "SPEC.md"),
        "EXAMPLES.feature": _read(spec_dir / "EXAMPLES.feature"),
        "BACKLOG.md": _read(spec_dir / "BACKLOG.md"),
        "WAVES.md": _read(spec_dir / "WAVES.md"),
        "LOOP.md": _read(spec_dir / "LOOP.md"),
        "GATES.md": _read(spec_dir / "GATES.md"),
        "VALIDATION.md": _read(spec_dir / "VALIDATION.md"),
    }

    required = ["SPEC.md", "EXAMPLES.feature", "BACKLOG.md"]
    if phase == "delivery":
        required += ["WAVES.md", "LOOP.md", "VALIDATION.md"]
    for name in required:
        if not (spec_dir / name).is_file():
            findings.append(Finding(
                "blocker", "missing-artifact",
                f"specs/{spec_dir.name}/{name}",
                f"{name} is required for the {phase} audit",
            ))

    spec_text = artifacts["SPEC.md"]
    feature_text = artifacts["EXAMPLES.feature"]
    backlog_text = artifacts["BACKLOG.md"]
    waves_text = artifacts["WAVES.md"]
    loop_text = artifacts["LOOP.md"]
    gates_text = artifacts["GATES.md"]
    validation_text = artifacts["VALIDATION.md"]

    scenarios = _parse_scenarios(feature_text)
    acs = _parse_acs(spec_text)
    backlog = _parse_backlog(backlog_text)
    waves = _parse_waves(waves_text)
    loop = _parse_loop(loop_text)
    gates = _parse_gates(gates_text)
    validation = _parse_validation(validation_text)

    scenario_waves = {w for s in scenarios for w in s["waves"]}
    backlog_ids = {it["id"] for it in backlog}

    if not scenarios:
        findings.append(Finding("blocker", "no-scenarios",
                                f"specs/{spec_dir.name}/EXAMPLES.feature",
                                "no Gherkin scenarios parsed"))
    if not acs:
        findings.append(Finding("blocker", "no-acceptance-criteria",
                                f"specs/{spec_dir.name}/SPEC.md",
                                "no acceptance-criteria rows parsed"))
    if not backlog:
        findings.append(Finding("blocker", "no-backlog-items",
                                f"specs/{spec_dir.name}/BACKLOG.md",
                                "no `## US<n>` / `## B<n>` items parsed"))

    # --- traceability -------------------------------------------------
    covered_waves, covered_names = set(), set()
    for ac in acs:
        refs = ac["refs"]
        tags = {int(w) for w in _TAG_RE.findall(refs)}
        names = {s["name"] for s in scenarios
                 if s["name"].lower() in refs.lower()}
        if not tags and not names:
            # A build/quality gate criterion ("`sh gradlew test` passes") is
            # verified by running the command, not by a Gherkin scenario.
            if _BUILD_CMD_RE.search(ac["criterion"]) or "gate" in refs.lower():
                continue
            findings.append(Finding(
                "blocker", "ac-no-scenario", f"SPEC.md:{ac['line']}",
                f"AC {ac['n']} has no scenario reference (name or @w tag)",
            ))
        for w in tags:
            if w not in scenario_waves:
                findings.append(Finding(
                    "blocker", "ac-unknown-wave", f"SPEC.md:{ac['line']}",
                    f"AC {ac['n']} references @w{w}, but no scenario is tagged @w{w}",
                ))
        covered_waves |= tags
        covered_names |= names

    for s in scenarios:
        if not s["waves"]:
            findings.append(Finding(
                "blocker", "scenario-untagged", f"EXAMPLES.feature:{s['line']}",
                f"scenario `{s['name']}` has no @w<N> tag",
            ))
        if not (s["waves"] & covered_waves) and s["name"] not in covered_names:
            findings.append(Finding(
                "concern", "scenario-uncovered", f"EXAMPLES.feature:{s['line']}",
                f"scenario `{s['name']}` is not referenced by any acceptance criterion",
            ))

    if waves:
        for s in scenarios:
            for w in s["waves"]:
                if w not in waves:
                    findings.append(Finding(
                        "blocker", "scenario-wave-missing",
                        f"EXAMPLES.feature:{s['line']}",
                        f"scenario `{s['name']}` is tagged @w{w}, but WAVES.md has no wave {w}",
                    ))
        for w, data in waves.items():
            if not data["items"]:
                findings.append(Finding(
                    "concern", "wave-empty", f"WAVES.md:{data['line']}",
                    f"wave {w} has no backlog items",
                ))
            for item in data["items"]:
                if item not in backlog_ids:
                    findings.append(Finding(
                        "blocker", "wave-unknown-item", f"WAVES.md:{data['line']}",
                        f"wave {w} references `{item}`, which is not in BACKLOG.md",
                    ))

    for it in backlog:
        if not it["waves"]:
            findings.append(Finding(
                "concern", "backlog-no-scenarios", f"BACKLOG.md:{it['line']}",
                f"{it['id']} has no `Scenarios:` tag",
            ))
        for w in it["waves"]:
            if waves and w not in waves:
                findings.append(Finding(
                    "blocker", "backlog-wave-missing", f"BACKLOG.md:{it['line']}",
                    f"{it['id']} references @w{w}, but WAVES.md has no wave {w}",
                ))
        for dep in it["deps"]:
            if f"US{dep}" not in backlog_ids and f"B{dep}" not in backlog_ids:
                findings.append(Finding(
                    "blocker", "backlog-unknown-dep", f"BACKLOG.md:{it['line']}",
                    f"{it['id']} depends on item #{dep}, which is not in BACKLOG.md",
                ))

    # --- unresolved spec markers --------------------------------------
    for name in ("SPEC.md", "EXAMPLES.feature", "BACKLOG.md"):
        for i, line in enumerate(artifacts[name].splitlines(), 1):
            if _UNRESOLVED_RE.search(line):
                findings.append(Finding(
                    "blocker", "unresolved-spec", f"{name}:{i}",
                    f"unresolved marker: {line.strip()[:110]}",
                ))

    # --- terminology vs product truth ---------------------------------
    # Copy must not promise capabilities the spec places out of scope.
    # Generic rule: capability nouns from SPEC.md Scope(out)/Non-goals
    # matched against scenario/backlog wording and shipped UI copy;
    # auth-phrase rule catches multi-word auth wording the term pass
    # cannot see. Concerns for the auditor, never blockers.
    cap_re = _capability_pattern(_capability_terms(spec_text))
    auth_disclaimed = bool(_AUTH_DISCLAIMER_RE.search(spec_text))

    def _capability_hits(text: str) -> list[str]:
        if _NEGATED_RE.search(text):
            return []
        hits = []
        if cap_re:
            h = _capability_hit(cap_re, text)
            if h:
                hits.append(h)
        if auth_disclaimed and _auth_claim_unnegated(text):
            m = _AUTH_CLAIM_RE.search(text)
            hits.append(m.group(0) if m else "auth")
        return hits

    if cap_re or auth_disclaimed:
        for name in ("EXAMPLES.feature", "BACKLOG.md"):
            deferred = False
            for i, line in enumerate(artifacts[name].splitlines(), 1):
                if _HEADING_RE.match(line):
                    deferred = bool(_OUT_OF_SCOPE_HEADING_RE.search(line))
                if deferred or _NEGATED_RE.search(line):
                    continue
                hits = _capability_hits(line)
                if hits:
                    findings.append(Finding(
                        "concern", "terminology-capability", f"{name}:{i}",
                        "wording implies out-of-scope capability "
                        f"({', '.join(hits)}): {line.strip()[:90]}",
                    ))

    # --- value contract (D017): advisory here, enforced by the G0 gate --
    vc_ok, vc_problems = value_contract_status(spec_text)
    if not vc_ok:
        findings.append(Finding(
            "concern", "value-contract-missing",
            f"specs/{spec_dir.name}/SPEC.md",
            "value contract is missing or unmeasurable: "
            + ", ".join(vc_problems[:4])
            + " (advisory — the Before: plan gate enforces it)",
        ))

    # --- claim verification -------------------------------------------
    checked_paths = 0
    for name in ("SPEC.md", "EXAMPLES.feature", "BACKLOG.md", "WAVES.md",
                 "LOOP.md", "GATES.md", "VALIDATION.md"):
        seen: set[str] = set()
        for token, line_no in _path_tokens(artifacts[name]):
            if token in seen or not _looks_like_path(token):
                continue
            seen.add(token)
            checked_paths += 1
            if _resolve(root, spec_dir, token) is not None:
                continue
            if _branch_like(token) and not (root / token).exists():
                continue
            context = artifacts[name].splitlines()[line_no - 1]
            idx = context.find(token)
            prefix = context[:idx] if idx >= 0 else context
            # "instead of `api.php`" / "no `src/legacy`" is a statement that
            # the path is absent, not a claim that it exists.
            if _NEGATED_RE.search(prefix[-90:]):
                continue
            current = bool(_CURRENT_RE.search(prefix))
            if phase == "delivery":
                severity = "blocker"
            elif current:
                severity = "blocker"
            else:
                severity = "concern"
            findings.append(Finding(
                severity, "missing-path", f"{name}:{line_no}",
                f"`{token}` does not exist"
                + (" (claimed as current)" if current else ""),
            ))

    for name in ("SPEC.md", "WAVES.md", "LOOP.md", "GATES.md", "VALIDATION.md"):
        for command, script, line_no in _command_scripts(artifacts[name]):
            if not (root / script).exists():
                findings.append(Finding(
                    "blocker", "missing-script", f"{name}:{line_no}",
                    f"`{command}` references `{script}`, which does not exist",
                ))

    for name in ("SPEC.md", "EXAMPLES.feature", "WAVES.md", "VALIDATION.md"):
        seen_endpoints: set[tuple[str, str]] = set()
        for method, path, line_no in _endpoints(artifacts[name]):
            if (method, path) in seen_endpoints:
                continue
            seen_endpoints.add((method, path))
            if _endpoint_in_code(root, method, path):
                continue
            severity = "blocker" if phase == "delivery" else "concern"
            findings.append(Finding(
                severity, "endpoint-not-found", f"{name}:{line_no}",
                f"{method} {path} was not found in source"
                + ("" if phase == "delivery" else " (expected if still planned)"),
            ))

    for name in ("SPEC.md", "WAVES.md", "VALIDATION.md"):
        for i, line in enumerate(artifacts[name].splitlines(), 1):
            for m in _ADR_RE.finditer(line):
                prefix = line[:m.start()].rstrip()
                qualifier = re.search(r"([A-Za-z0-9_.-]+)$", prefix)
                # "ddd-eshop ADR 0003" names another repo's ADR, not this one.
                if qualifier and (
                    "-" in qualifier.group(1) or "." in qualifier.group(1)
                ):
                    continue
                if not _adr_exists(root, m.group(1)):
                    findings.append(Finding(
                        "concern", "missing-adr", f"{name}:{i}",
                        f"ADR {m.group(1)} is referenced but not found under docs/adr/",
                    ))

    # --- delivery evidence --------------------------------------------
    if phase == "delivery":
        for n, data in waves.items():
            row = loop["waves"].get(n)
            if not row:
                findings.append(Finding(
                    "blocker", "loop-missing-wave", "LOOP.md",
                    f"wave {n} is planned but has no LOOP.md row",
                ))
                continue
            if row["status"] == "done":
                if _placeholder_evidence(row["evidence"]):
                    findings.append(Finding(
                        "blocker", "placeholder-wave-evidence", "LOOP.md",
                        f"wave {n} is done but its evidence is a placeholder: "
                        f"{row['evidence'] or '(empty)'}",
                    ))
                if row["pr"] in ("", "—", "-"):
                    findings.append(Finding(
                        "concern", "wave-no-pr", "LOOP.md",
                        f"wave {n} is done but records no PR reference",
                    ))
        for n in loop["waves"]:
            if n not in waves:
                findings.append(Finding(
                    "concern", "loop-extra-wave", "LOOP.md",
                    f"LOOP.md records wave {n}, which is not in WAVES.md",
                ))
        if loop["status"] == "done" and any(
            loop["waves"].get(n, {}).get("status") != "done" for n in waves
        ):
            findings.append(Finding(
                "blocker", "done-with-pending-waves", "LOOP.md",
                "feature status is done while waves are not done",
            ))

        # TDD proof lives in the wave's evidence bundle: an ordered
        # red -> green -> refactor step sequence (ship_loop enforces it
        # at complete; here it is reported, not re-blocked).
        tdd: dict[int, dict] = {}
        for row in evidence_bundles.list_bundles(root, feature=spec_dir.name):
            w = row.get("wave")
            if isinstance(w, int) and w > 0 and w not in tdd:
                try:
                    tdd[w] = evidence_bundles.tdd_proof(
                        evidence_bundles.load(row["bundle"])
                    )
                except evidence_bundles.EvidenceError:
                    continue
        for n in waves:
            if loop["waves"].get(n, {}).get("status") != "done":
                continue
            proof = tdd.get(n)
            if proof is None:
                findings.append(Finding(
                    "concern", "tdd-missing", "LOOP.md",
                    f"wave {n} is done but no evidence bundle records "
                    "TDD red→green→refactor steps",
                ))
            elif not proof["ok"]:
                findings.append(Finding(
                    "concern", "tdd-missing", "LOOP.md",
                    f"wave {n} TDD proof incomplete: "
                    + "; ".join(proof["problems"][:2]),
                ))

        for gid, g in gates.items():
            if g["before"] and g["before"] not in (
                "spec", "plan", "validate", "finish"
            ) and not re.match(r"^wave:\d+$", g["before"]):
                findings.append(Finding(
                    "blocker", "gate-bad-phase", "GATES.md",
                    f"gate {gid} has an invalid Before value: `{g['before']}`",
                ))
            state = loop["gates"].get(gid)
            if not state:
                findings.append(Finding(
                    "blocker", "gate-no-state", "LOOP.md",
                    f"gate {gid} is defined but has no status row",
                ))
                continue
            status = state["status"]
            evidence = state["evidence"]
            if status == "met":
                if _placeholder_evidence(evidence):
                    findings.append(Finding(
                        "blocker", "placeholder-gate-evidence", "LOOP.md",
                        f"gate {gid} is met but its evidence is a placeholder: "
                        f"{evidence or '(empty)'}",
                    ))
                if g["check"].lower().startswith("file:"):
                    rel = g["check"].split(":", 1)[1].strip()
                    if rel and not (root / rel).exists():
                        findings.append(Finding(
                            "blocker", "gate-file-missing", "LOOP.md",
                            f"gate {gid} cites `{rel}`, which does not exist",
                        ))
            elif status == "waived":
                if "waived by" not in evidence.lower():
                    findings.append(Finding(
                        "blocker", "gate-waiver-unowned", "LOOP.md",
                        f"gate {gid} is waived without a named human",
                    ))
            elif g["blocking"] and status in ("pending", "failed"):
                findings.append(Finding(
                    "blocker", "gate-unmet", "LOOP.md",
                    f"blocking gate {gid} is {status} at delivery time",
                ))

        if not validation:
            findings.append(Finding(
                "blocker", "no-validation-rows", "VALIDATION.md",
                "no traceability rows parsed — validation is not evidence",
            ))
        manual = _manual_acs(validation_text)
        for row in validation:
            ev = row["evidence"]
            weak = ev.lower().startswith("(weak)")
            placeholder = ev in ("", "—", "-", "–")
            if not (weak or placeholder):
                continue
            if row["n"] in manual:
                continue
            code = "ac-weak-evidence" if weak else "ac-no-evidence"
            findings.append(Finding(
                "blocker", code, "VALIDATION.md",
                f"AC {row['n']} has "
                f"{'only weak token-match' if weak else 'no'} test evidence "
                "and no `## Manual verification` entry",
            ))
        if re.search(r"Scenarios:\s*0\b", validation_text) or re.search(
            r"\b0/0\b", validation_text
        ):
            findings.append(Finding(
                "blocker", "validation-empty", "VALIDATION.md",
                "validation reports zero scenarios",
            ))
        gaps = re.search(r"^##\s+Gaps\s*$", validation_text, re.M)
        if gaps:
            rest = validation_text[gaps.end():]
            nxt = re.search(r"^##\s+", rest, re.M)
            block = rest[:nxt.start()] if nxt else rest
            bullets: list[list[str]] = []
            indent = None
            for line in block.splitlines():
                m = re.match(r"^(\s*)-\s+", line)
                if m:
                    if indent is None:
                        indent = len(m.group(1))
                    if len(m.group(1)) == indent:
                        bullets.append([line.strip()])
                        continue
                if bullets and line.strip():
                    bullets[-1].append(line.strip())
            for parts in bullets:
                first = parts[0]
                if "none" in first.lower():
                    continue
                # A bullet that explains scope or dismisses an artifact is not
                # an unresolved gap, even when the qualifier wraps to the next
                # line.
                if _GAP_NOISE_RE.search(" ".join(parts)):
                    continue
                findings.append(Finding(
                    "concern", "validation-gap", "VALIDATION.md",
                    f"unresolved validation gap: {first[2:][:110]}",
                ))
        for i, line in enumerate(validation_text.splitlines(), 1):
            if _ASPIRATIONAL_RE.search(line):
                findings.append(Finding(
                    "concern", "aspirational-validation", f"VALIDATION.md:{i}",
                    f"validation uses future language: {line.strip()[:110]}",
                ))

    # --- scope drift / shipped-code markers ---------------------------
    checked_changed = 0
    scope = _scope_paths(root, spec_dir, spec_text)
    if phase == "delivery":
        changed_files, source = _changed_files(root, changed, base)
        checked_changed = len(changed_files)
        if not changed_files:
            findings.append(Finding(
                "unverified", "scope-not-checked", "git",
                f"scope drift not checked ({source})",
            ))
        elif not scope:
            findings.append(Finding(
                "unverified", "scope-no-paths", "SPEC.md",
                "scope drift not checked — no in-scope paths recorded",
            ))
        else:
            for path in changed_files:
                if _out_of_scope_exempt(path) or _in_scope(path, scope):
                    continue
                findings.append(Finding(
                    "concern", "scope-drift", path,
                    "changed file is outside the spec's in-scope paths",
                ))
        for path in changed_files:
            p = root / path
            if p.suffix.lower() not in _CODE_EXTS or not p.is_file():
                continue
            for i, line in enumerate(_read(p).splitlines(), 1):
                if _unfinished_marker(line):
                    findings.append(Finding(
                        "concern", "unfinished-code", f"{path}:{i}",
                        f"shipped code contains an unfinished marker: {line.strip()[:100]}",
                    ))
                    break

        if cap_re or auth_disclaimed:
            for path in changed_files:
                p = root / path
                if p.suffix.lower() not in _COPY_EXTS or not p.is_file():
                    continue
                for i, line in enumerate(_read(p).splitlines(), 1):
                    hit = next(
                        (h for f in _copy_fragments(line)
                         for h in _capability_hits(f)),
                        None,
                    )
                    if hit is not None:
                        findings.append(Finding(
                            "concern", "terminology-capability",
                            f"{path}:{i}",
                            "user-facing copy implies an out-of-scope "
                            f"capability (`{hit}`): "
                            f"`{line.strip()[:80]}`",
                        ))
                        break

    # --- assemble ------------------------------------------------------
    findings = _trim(findings)
    counts = {
        "blockers": sum(1 for f in findings if f.severity == "blocker"),
        "concerns": sum(1 for f in findings if f.severity == "concern"),
        "unverified": sum(1 for f in findings if f.severity == "unverified"),
    }
    title = f"# Delivery audit — {spec_dir.name} ({phase})"
    out = [
        title,
        "",
        f"- Repo: `{_display_path(root)}`",
        f"- Spec: `{_rel(root, spec_dir)}`",
        f"- Generated: {_now()}",
        f"- Phase: **{phase}**",
        f"- Findings: **{counts['blockers']} blockers · "
        f"{counts['concerns']} concerns · {counts['unverified']} unverified**",
        "- This is a deterministic evidence brief, not a verdict. The "
        "`delivery-auditor` re-verifies it and fills the verdict.",
        "",
        "## What was checked",
        "",
        f"- Acceptance criteria: {len(acs)}",
        f"- Scenarios: {len(scenarios)} ({len(scenario_waves)} wave tags)",
        f"- Backlog items: {len(backlog)}",
        f"- Waves: {len(waves)}",
        f"- Gates: {len(gates)}",
        f"- Validation rows: {len(validation)}",
        f"- Path claims checked: {checked_paths}",
        f"- Changed files: {checked_changed}",
        f"- In-scope paths: {', '.join(f'`{s}`' for s in scope[:8]) or 'none recorded'}",
        "",
    ]
    for severity, label in (
        ("blocker", "Blockers"),
        ("concern", "Concerns"),
        ("unverified", "Unverified"),
    ):
        rows = [f for f in findings if f.severity == severity]
        out += [f"## {label}", ""]
        if rows:
            for f in rows:
                out.append(f"- [{f.code}] `{f.where}` — {f.message}")
        elif severity == "blocker":
            out.append("None. This is not a pass: verify semantics before accepting.")
        else:
            out.append("None.")
        out.append("")

    out += [
        "## Verdict (agent fills after verifying the code)",
        "",
        "```",
        "AUDIT: PASS | CONCERNS | BLOCK",
        "PHASE: spec | delivery",
        "BLOCKERS: <confirmed count and why>",
        "CONCERNS: <accepted concerns and why>",
        "UNVERIFIED: <what could not be checked>",
        "EVIDENCE: <commands run, files read, tests observed>",
        "```",
        "",
        "Rules: `BLOCK` on any confirmed blocker, hallucinated claim, or",
        "unproven acceptance criterion. `CONCERNS` only when every remaining",
        "item is non-blocking and explicitly accepted. `PASS` only when all",
        "three lists are empty. Never mark `PASS` from this brief alone.",
    ]
    return "\n".join(out) + "\n", findings


def _trim(findings: list[Finding]) -> list[Finding]:
    """Cap repeated codes so one bad pattern does not drown the brief."""
    per_code: dict[str, int] = {}
    out = []
    for f in findings:
        per_code[f.code] = per_code.get(f.code, 0) + 1
        if per_code[f.code] <= _MAX_PER_CODE and len(out) < _MAX_FINDINGS:
            out.append(f)
    return out


@skill
def review_delivery(
    repo_path: str = ".",
    spec_dir: str = "",
    phase: str = "delivery",
    changed: str = "",
    base: str = "",
    write: bool = False,
    force: bool = False,
) -> str:
    """Audit a feature's spec/delivery against the repo and emit an evidence brief.

    Reads `specs/<feature>/` and checks traceability (AC -> scenario -> wave ->
    backlog -> LOOP), claim existence (paths, scripts, endpoints, ADRs),
    evidence integrity (wave/gate/validation), scope drift, and unfinished
    markers. Emits findings by severity plus a verdict block; it never judges
    semantics or emits a verdict — the `delivery-auditor` subagent does that.

    Params:
      repo_path: Repository root.
      spec_dir: Feature dir (`specs/<feature>`); defaults to the first
        unfinished feature under `specs/`.
      phase: `spec` (before planning waves), `delivery` (before validation or
        finish), or `all` (both).
      changed: Comma/space-separated changed files; inferred from git when empty.
      base: Git base ref for the diff (default: origin/main, origin/master,
        main, or master).
      write: Write `SPEC-AUDIT.md` / `DELIVERY-AUDIT.md` next to the spec.
      force: Overwrite an existing audit file.
    """
    root = Path(repo_path).resolve()
    if not root.is_dir():
        return f"ERROR: {repo_path} is not a directory"
    if phase not in ("spec", "delivery", "all"):
        return "ERROR: --phase must be spec|delivery|all"

    if spec_dir:
        d = Path(spec_dir)
        if not d.is_absolute():
            d = (root / d).resolve()
        if not d.is_dir():
            return f"ERROR: spec_dir {spec_dir} not found"
    else:
        specs = root / "specs"
        if not specs.is_dir():
            return "ERROR: no specs/ directory — scaffold a feature first"
        candidates = [
            x for x in sorted(specs.iterdir())
            if x.is_dir() and not x.name.startswith(".")
        ]
        if not candidates:
            return "ERROR: no feature directories under specs/"
        d = candidates[0]

    phases = ["spec", "delivery"] if phase == "all" else [phase]
    briefs, written = [], []
    for ph in phases:
        brief, _ = _audit(root, d, ph, changed, base)
        briefs.append(brief)
        if not write:
            continue
        target = d / ("SPEC-AUDIT.md" if ph == "spec" else "DELIVERY-AUDIT.md")
        if target.exists() and not force:
            briefs.append(f"\nERROR: {_rel(root, target)} exists — pass --force to overwrite")
            continue
        target.write_text(brief)
        written.append(_rel(root, target))

    out = "\n\n---\n\n".join(briefs)
    if written:
        out += "\n" + "\n".join(f"Wrote {w}" for w in written)
    return out
