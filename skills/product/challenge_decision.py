"""Challenge a design/architecture decision: build a rigorous review brief.

Reads a decision from an ADR, a spec's `## Decisions` section, or inline text,
then produces a structured challenge brief the agent uses to review it:

- record completeness (context, decision, alternatives, consequences, forces,
  evidence) and a readiness hint — not a design verdict;
- design signals scanned from the referenced code paths (heuristic, labelled
  as such): framework leakage into the domain, missing tests, anemic models,
  transaction/event/invariant presence, external calls in the core;
- alternative "design moves" to test, chosen by decision type;
- lens-specific questions for architecture, DDD, testability, craftsmanship,
  and decision-record quality, each with "good looks like" criteria;
- a scorecard and verdict block the agent fills after reading the code.

The skill never claims a design is good or bad: it assembles evidence and
questions so the agent can discover the better design. Deterministic.
"""

import os
import re
from datetime import datetime, timezone
from pathlib import Path

from openharness.skill import skill

_SKIP_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build",
    "vendor", ".chroma", ".next", ".nuget", "bin", "obj", "target",
    ".gradle", "Pods", "coverage",
}
_CODE_EXTS = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".kt", ".cs", ".go", ".rs",
    ".rb", ".php", ".swift", ".m", ".scala", ".groovy",
}
_MAX_FILE = 256 * 1024
_MAX_FILES = 400

_HEADING_RE = re.compile(r"^##\s+(.+?)\s*$", re.M)
_BULLET_RE = re.compile(r"^(?:[-*+]|\d+[.)])\s+(.{3,})$")
_ALT_MARKER_RE = re.compile(r"\b(?:options?|alternatives?)\b", re.I)
_CONTRAST_RE = re.compile(r"\s+(?:vs\.?|versus)\s+", re.I)
_SENTENCE_SPLIT_RE = re.compile(r"""(?<=[.!?])\s+(?=[A-Z("'])""")
_OPTION_PREFIX_RE = re.compile(
    r"^\s*(?:the\s+)?(?:options?|alternatives?)\s+"
    r"(?:were|are|include|included|considered)?\s*[:\-—]?\s*",
    re.I,
)
_EVIDENCE_RE = re.compile(
    r"`[^`]+`|https?://|\b[\w./-]+\.(?:md|py|ts|tsx|js|java|kt|cs|go|rb|sql|json|ya?ml)\b"
    r"|\bADR[- ]?\d+\b|#\d+|\b\d+(?:\.\d+)?\s*(?:ms|s|%|rps|qps|MB|GB)\b",
    re.I,
)
_REVERSIBLE_RE = re.compile(
    r"\b(reversible|irreversible|one-way|two-way|rollback|roll back|revert|"
    r"feature[- ]flag|migration path|strangler)\b", re.I)
_FORCES_RE = re.compile(
    r"\b(constraint|budget|deadline|compliance|regulat\w*|team|latency|"
    r"throughput|cost|existing|legacy|contract|SLA|quality attribute)\b", re.I)
_FRAMEWORK_RE = re.compile(
    r"^\s*(?:from|import)\s+(fastapi|flask|django|sqlalchemy|pydantic|"
    r"springframework|org\.springframework|javax\.persistence|"
    r"jakarta\.persistence|typeorm|prisma|sequelize|express|react|next)\b",
    re.M)
_EXTERNAL_RE = re.compile(
    r"(?:requests\.|httpx\.|axios\.|fetch\(|RestTemplate|WebClient|"
    r"HttpClient|http\.Get|URLSession)"
    r"|^\s*(?:import|from)\s+(?:requests|httpx|axios)\b",
    re.M)
_GETTER_RE = re.compile(
    r"^\s*(?:(?:public|private|protected)\s+)?(?:def\s+)?"
    r"(?:get|set)[A-Z_]\w*\s*\(", re.M)
_DEF_RE = re.compile(r"^\s*(?:public|private|protected|def|function|func)\s+\w+", re.M)
_DOMAIN_EVENT_RE = re.compile(r"\b\w+(?:Event|event)\b")
_INVARIANT_RE = re.compile(r"\b(invariant|assert|guard|ensure|raise|throw)\b", re.I)

_TYPE_WORDS = {
    "architecture": ["boundary", "module", "service", "monolith", "microservice",
                     "layer", "coupling", "deploy", "deployment", "context map",
                     "hexagonal", "modular"],
    "data": ["schema", "migration", "migrate", "consistency", "consistent",
             "transaction", "transactional", "eventual", "aggregate", "database",
             "table", "index", "idempotent", "idempotency"],
    "api": ["endpoint", "contract", "version", "versioning", "rest", "graphql",
            "grpc", "protobuf", "openapi", "asyncapi", "websocket", "payload",
            "backward", "breaking", "deprecat"],
    "persistence": ["orm", "repository", "unit of work", "jpa", "entity",
                    "active record", "query", "dao"],
    "integration": ["webhook", "queue", "event bus", "third-party", "external",
                    "acl", "anti-corruption", "retry", "retries", "timeout",
                    "timeouts", "idempotent", "idempotency"],
    "events": ["kafka", "rabbitmq", "sqs", "sns", "pub/sub", "pubsub",
               "producer", "consumer", "topic", "message broker",
               "event-driven", "event stream", "asyncapi"],
    "security": ["auth", "authentication", "authorization", "secret", "token",
                 "threat", "privilege", "encrypt", "encryption", "audit"],
    "domain": ["ubiquitous", "bounded context", "aggregate", "invariant",
               "domain event", "value object", "entity"],
    "ux": ["user", "screen", "flow", "accessibility", "journey", "form"],
    "process": ["process", "team", "workflow", "ci", "review", "ownership"],
}
_HIGH_IMPACT = {"architecture", "data", "persistence", "integration", "security", "events"}


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _read(path: Path) -> str:
    try:
        return path.read_text(errors="ignore")
    except OSError:
        return ""


def _norm(text: str, limit: int = 400) -> str:
    return " ".join(text.split())[:limit]


def _rel(root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path)


def _title(text: str, fallback: str) -> str:
    m = re.search(r"^#\s+(.+)$", text, re.M)
    if m:
        return _norm(m.group(1), 100)
    for line in text.splitlines():
        s = line.strip()
        if s:
            return _norm(s.lstrip("# "), 100)
    return fallback


def _sections(text: str) -> dict[str, str]:
    parts = _HEADING_RE.split(text)
    out: dict[str, str] = {}
    if parts:
        out["__preamble__"] = parts[0]
    for i in range(1, len(parts) - 1, 2):
        out[parts[i].strip().lower()] = parts[i + 1]
    return out


def _section(sections: dict[str, str], *names: str) -> str:
    # Exact heading first: `## Decision` must beat `## Decision Drivers`.
    for name in names:
        if name in sections:
            return sections[name]
    for key, body in sections.items():
        if any(n in key for n in names):
            return body
    return ""


def _options(body: str) -> list[str]:
    opts = []
    for line in body.splitlines():
        m = _BULLET_RE.match(line.strip())
        if m:
            opts.append(_norm(m.group(1), 160))
    return opts


def _paragraphs(text: str):
    """Join hard-wrapped lines so a sentence split is not fooled by line breaks."""
    block: list[str] = []
    for line in text.splitlines():
        s = line.strip()
        if not s:
            if block:
                yield " ".join(block)
                block = []
            continue
        block.append(s)
    if block:
        yield " ".join(block)


def _inline_alternatives(text: str) -> list[str]:
    """Options named in prose, e.g. "Options were A vs. B".

    Deliberately conservative: a noun marker ("option"/"alternative") or a
    real contrast ("vs."/"versus") must be present, questions are ignored,
    and rhetorical "rather than"/"instead of" do not count. A bare list of
    decisions (a spec's `## Decisions`) does not.
    """
    out: list[str] = []
    for paragraph in _paragraphs(text):
        paragraph = paragraph.replace("**", "").replace("`", "")
        for sentence in _SENTENCE_SPLIT_RE.split(paragraph):
            sentence = sentence.strip()
            sentence = re.sub(r"^[-*+]\s+", "", sentence)
            if not sentence or sentence.endswith("?"):
                continue
            if not (_ALT_MARKER_RE.search(sentence) or _CONTRAST_RE.search(sentence)):
                continue
            sides = _CONTRAST_RE.split(sentence, maxsplit=1)
            if len(sides) == 2:
                left = _OPTION_PREFIX_RE.sub("", sides[0]).strip(" ,;:-")
                right = re.split(r";", sides[1], maxsplit=1)[0].strip(" ,;:-")
                for side in (left, right):
                    if len(side) >= 3:
                        out.append(_norm(side, 160))
            else:
                out.append(_norm(sentence, 160))
    seen, uniq = set(), []
    for alt in out:
        key = alt.lower()
        if key not in seen:
            seen.add(key)
            uniq.append(alt)
    return uniq[:8]


def _alternatives(parts: dict, kind: str) -> list[str]:
    body = _section(
        parts["sections"], "alternative", "options considered", "option",
        "trade-off", "tradeoff",
    )
    opts = _options(body) if body else []
    if len(opts) < 2:
        seen = {o.lower() for o in opts}
        for alt in _inline_alternatives(parts["full"]):
            if alt.lower() not in seen:
                seen.add(alt.lower())
                opts.append(alt)
    return opts


def _detect_types(text: str) -> list[str]:
    low = text.lower()
    scores = {}
    for name, words in _TYPE_WORDS.items():
        score = sum(
            len(re.findall(rf"\b{re.escape(w)}\b", low)) for w in words
        )
        if score:
            scores[name] = score
    ranked = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
    return [name for name, _ in ranked[:2]] or ["architecture"]


def _source(repo: Path, spec_dir: str, adr: str, decision: str):
    """Return (parts, label, write_dir, error)."""
    sections: dict[str, str] = {}
    full = ""
    label = ""
    write_dir: Path | None = None

    if adr:
        path = Path(adr)
        if not path.is_absolute():
            path = repo / adr
        if not path.is_file():
            return None, "", None, f"ERROR: ADR not found: {adr}"
        full = _read(path)
        sections = _sections(full)
        label = _rel(repo, path)
        write_dir = path.parent
    elif spec_dir:
        d = Path(spec_dir)
        if not d.is_absolute():
            d = repo / spec_dir
        spec = d / "SPEC.md"
        if not spec.is_file():
            return None, "", None, f"ERROR: SPEC.md not found in {spec_dir}"
        full = _read(spec)
        sections = _sections(full)
        decisions = _section(sections, "decisions", "decision log")
        if not decisions.strip():
            return None, "", None, (
                f"ERROR: no `## Decisions` content in {_rel(repo, spec)} — "
                "record the decision first or pass --decision"
            )
        label = f"{_rel(repo, spec)} (## Decisions)"
        write_dir = d
    elif decision:
        full = decision
        sections = _sections(full)
        label = "inline --decision"
        write_dir = None
    else:
        return None, "", None, (
            "ERROR: pass --adr=<path>, --spec_dir=<dir>, or --decision=\"<text>\""
        )

    kind = "adr" if adr else ("spec" if spec_dir else "inline")
    context = _section(sections, "context", "problem", "background")
    if kind == "spec":
        context = "\n".join(
            x for x in (context, _section(sections, "scope")) if x.strip()
        )
        body = _section(sections, "decisions", "decision log")
    else:
        body = _section(sections, "decision", "proposal", "approach")
    consequences = _section(
        sections, "consequence", "trade-off", "tradeoff", "impact", "risk"
    )
    if kind == "spec":
        # A spec records consequences as what the decision deliberately
        # excludes; Scope (out)/Non-goals are the spec's equivalent.
        consequences = "\n".join(
            x for x in (
                consequences,
                _section(sections, "scope (out)", "out of scope",
                         "non-goal", "non-goals"),
            ) if x.strip()
        )
    if kind == "inline" and not body:
        body = full
    parts = {
        "full": full,
        "kind": kind,
        "sections": sections,
        "context": context,
        "decision": body,
        "consequences": consequences,
        "alternatives": _alternatives(
            {"full": full, "sections": sections}, kind
        ),
    }
    return parts, label, write_dir, ""


def _completeness(parts: dict) -> list[tuple[str, bool, str]]:
    text = parts["full"]
    alts = parts["alternatives"]
    consequence_hint = "record positive and negative consequences"
    if parts.get("kind") == "spec":
        consequence_hint += (
            " or state what the decision explicitly excludes (Scope out / Non-goals)"
        )
    return [
        ("context", len(_norm(parts["context"], 2000)) >= 40,
         "state the problem, users, and forces driving the decision"),
        ("decision", len(_norm(parts["decision"], 4000)) >= 40,
         "state the chosen option in one or two sentences"),
        ("alternatives", len(alts) >= 2,
         "list at least two credible alternatives, including the simplest one"),
        ("consequences", len(_norm(parts["consequences"], 2000)) >= 20,
         consequence_hint),
        ("forces", bool(_FORCES_RE.search(text)),
         "name the constraints and quality attributes that dominate"),
        ("evidence", bool(_EVIDENCE_RE.search(text)),
         "link code, benchmarks, tickets, or ADRs that support the claim"),
    ]


def _readiness(checks: list[tuple[str, bool, str]], types: list[str]) -> tuple[str, list[str]]:
    missing = [name for name, ok, _ in checks if not ok]
    core = {"context", "decision", "consequences"}
    if core & set(missing):
        return "INCOMPLETE", missing
    if missing:
        return "CHALLENGE", missing
    return ("CHALLENGE" if set(types) & _HIGH_IMPACT else "READY"), missing


def _candidate_paths(root: Path, raw: str, text: str) -> list[Path]:
    found: list[Path] = []
    if raw:
        for token in re.split(r"[,\s]+", raw.strip()):
            if token:
                found.append(Path(token) if Path(token).is_absolute() else root / token)
    if not found:
        # Infer code paths only. A spec that cites `specs/PRODUCT.md` or an
        # ADR should not be "inspected" as source; if only docs are named,
        # the review is honestly document-only.
        for token in re.findall(r"`([^`]+)`", text):
            t = token.strip()
            if not t or t.startswith(("http://", "https://")):
                continue
            p = Path(t) if Path(t).is_absolute() else root / t
            if p.is_dir() or p.suffix.lower() in _CODE_EXTS:
                found.append(p)
    out, seen = [], set()
    for p in found:
        key = str(p)
        if key not in seen and p.exists():
            seen.add(key)
            out.append(p)
    return out[:12]


def _code_files(path: Path):
    if path.is_file():
        try:
            if path.suffix.lower() in _CODE_EXTS and path.stat().st_size <= _MAX_FILE:
                yield path
        except OSError:
            return
        return
    count = 0
    for dirpath, dirnames, filenames in os.walk(path):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS and not d.startswith(".")]
        for name in filenames:
            p = Path(dirpath) / name
            try:
                size = p.stat().st_size
            except OSError:
                continue
            if p.suffix.lower() in _CODE_EXTS and size <= _MAX_FILE:
                yield p
                count += 1
                if count >= _MAX_FILES:
                    return


def _test_files(root: Path):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS and not d.startswith(".")]
        for name in filenames:
            low = name.lower()
            if any(m in low for m in ("test", "spec")) and Path(name).suffix.lower() in _CODE_EXTS:
                yield Path(dirpath) / name


def _is_domain_path(path: Path) -> bool:
    parts = {p.lower() for p in path.parts}
    return bool(parts & {"domain", "core", "model", "models", "entities",
                         "aggregates", "business"}) or "domain" in path.name.lower()


def _signals(root: Path, paths: list[Path]) -> list[str]:
    signals: list[str] = []
    if not paths:
        return ["no code paths referenced — the review is document-only"]

    tests = list(_test_files(root))
    test_text = "\n".join(_read(t) for t in tests[:200])

    for path in paths:
        rel = _rel(root, path)
        files = list(_code_files(path))
        domain = _is_domain_path(path)
        if domain:
            signals.append(f"`{rel}` looks like a domain/core path — checking layering purity")
        if files and Path(rel).suffix.lower() in _CODE_EXTS:
            referenced = Path(rel).stem in test_text
        else:
            stems = {f.stem for f in files}
            referenced = bool(stems) and any(s in test_text for s in stems)
        if files and not referenced:
            signals.append(f"`{rel}` — no test file references this code (heuristic)")
        if not domain and files:
            signals.append(
                f"`{rel}` — {len(files)} source file(s); not a domain path, "
                "so layering checks were skipped"
            )

        framework_hits = 0
        external_hits = 0
        events = 0
        invariants = 0
        anemic = 0
        for f in files:
            text = _read(f)
            frel = _rel(root, f)
            if domain and _FRAMEWORK_RE.search(text):
                framework_hits += 1
                if framework_hits <= 3:
                    signals.append(
                        f"`{frel}` — domain code imports a framework/ORM "
                        "(layering risk: policy depends on mechanism)"
                    )
            if domain and _EXTERNAL_RE.search(text):
                external_hits += 1
                if external_hits <= 2:
                    signals.append(
                        f"`{frel}` — domain code performs external I/O "
                        "(testability risk: no seam)"
                    )
            events += len(_DOMAIN_EVENT_RE.findall(text))
            invariants += len(_INVARIANT_RE.findall(text))
            getters = len(_GETTER_RE.findall(text))
            defs = len(_DEF_RE.findall(text))
            if domain and getters >= 3 and defs and getters / defs >= 0.5:
                anemic += 1
        if domain and framework_hits == 0 and external_hits == 0 and files:
            signals.append(f"`{rel}` — no framework/IO imports detected in domain code (good)")
        if domain and events:
            signals.append(f"`{rel}` — domain-event vocabulary present ({events} references)")
        if domain and invariants:
            signals.append(f"`{rel}` — invariant/guard vocabulary present ({invariants} references)")
        if anemic:
            signals.append(
                f"`{rel}` — {anemic} file(s) look getter/setter-heavy "
                "(possible anemic model — verify behavior lives elsewhere)"
            )
        if not files:
            signals.append(f"`{rel}` — no source files found to inspect")
    return signals[:14]


def _style(root: Path) -> str:
    try:
        names = {d.name.lower() for d in root.iterdir() if d.is_dir()}
    except OSError:
        return ""
    known = {
        "domain/application/infrastructure": {"domain", "application", "infrastructure"},
        "ports/adapters (hexagonal)": {"ports", "adapters"},
        "layered (controllers/services/repositories)": {"controllers", "services", "repositories"},
        "modular (modules/features)": {"modules", "features"},
    }
    for label, keys in known.items():
        if keys & names:
            return f"detected `{label}` layout at the repo root"
    return ""


_DESIGN_MOVES = {
    "architecture": [
        "Can this be a module inside the current deployable before it becomes a service?",
        "Which dependency can be inverted so the core owns the interface?",
        "What is the smallest reversible step that tests the boundary?",
    ],
    "data": [
        "Which invariant spans more than one aggregate, and does the transaction span it too?",
        "Can the write model be separated from read shapes without splitting the database?",
        "What is the migration and rollback path for existing data?",
    ],
    "persistence": [
        "Is the model domain-shaped or table-shaped? Where does mapping happen?",
        "Is there one repository boundary per aggregate, or a generic DAO?",
        "Who owns transaction boundaries — the use case, the repository, or the framework?",
    ],
    "api": [
        "Is this a public contract or an implementation detail? Who depends on it?",
        "How will it version, and what is the backward-compatibility promise?",
        "Are errors part of the contract — consistent shape, codes, retry semantics — or an afterthought?",
        "Is the contract documented where consumers can find it (OpenAPI, AsyncAPI, schema registry, docs site), and is the doc generated from code or hand-maintained?",
        "Which fields and operations are stable vs experimental, and what is the deprecation path?",
        "Is authn/authz explicit per operation with least privilege, and is that visible in the docs?",
        "Are writes idempotent where clients can retry (idempotency keys, natural keys, upserts)?",
    ],
    "events": [
        "Is the event schema versioned and owned by the producer; how do consumers tolerate unknown or missing fields?",
        "What are the delivery guarantees (at-least/at-most/exactly-once) and the dedup strategy for consumers?",
        "What happens on poison messages — DLQ, retry/backoff policy, ordering requirements?",
        "Is the contract discoverable (schema registry, AsyncAPI, catalog) so consumers don't guess payloads?",
        "Are events facts about the past with minimal payloads, or disguised commands coupling producer and consumer?",
    ],
    "integration": [
        "Is an anti-corruption layer needed, or will the external model leak inward?",
        "What happens on timeout, duplicate delivery, partial failure, and replay?",
        "Can this be async where the business allows it, removing temporal coupling?",
    ],
    "security": [
        "What is the threat model, and which asset is actually being protected?",
        "Where are secrets stored, rotated, and audited?",
        "What is the least privilege this component needs?",
    ],
    "domain": [
        "What is the ubiquitous language, and which terms are overloaded across contexts?",
        "Which aggregate protects each invariant, and where is the consistency boundary?",
        "Are domain events facts about the past, or disguised commands?",
    ],
    "ux": [
        "Which user journey does this serve, including empty, error, and slow states?",
        "What is the accessibility and keyboard path?",
        "Where does the UI hold state that belongs to the domain?",
    ],
    "process": [
        "What feedback loop proves this process works, and how fast is it?",
        "Who owns it when it fails, and what is the escalation path?",
        "Can it be simpler without losing the guarantee?",
    ],
}

_LENSES = [
    ("Problem & forces", [
        "What user/business outcome does this serve, and what breaks if we do nothing?",
        "Which quality attributes actually drive it (correctness, latency, cost, operability, compliance, time-to-market)? Rank them.",
        "Which constraints are fixed (budget, deadline, team, contracts) and which are assumed?",
        "Who owns this decision, and who must live with the consequences?",
    ], "The dominant force is named, and \"do nothing\" is treated as a real option."),
    ("Value & economics", [
        "What is the value gap: who bears the current cost, and how painful or frequent is it?",
        "Which outcome indicator and baseline prove the gap closed, and over what review window?",
        "What is the full-lifecycle cost (build, operate, adopt, migrate, support) and what benefit justifies it?",
        "Will users actually choose this? What adoption signal would show they do?",
        "Which quality dimensions does this affect — product (user task), system (correctness, security, reliability, operability) and business (TCO, adoption, adaptability)? Name any it makes worse.",
        "What is the simplest intervention that produces the same outcome — including not building it?",
    ], "The value gap, a numeric target, a lifecycle cost hypothesis and an adoption signal are explicit; quality tradeoffs are named; 'do nothing' is a real option."),
    ("Alternatives & tradeoffs", [
        "What are at least two credible alternatives, including the simplest thing that could work?",
        "For each: what does it make easy, what does it make hard, and what does it cost to reverse?",
        "Is this a one-way or two-way door? If one-way, what evidence justifies it?",
        "What would have to be true for the chosen option to be wrong?",
    ], "A tradeoff matrix names winners and losers; reversibility is explicit; no strawman options."),
    ("Domain fit (DDD)", [
        "Which bounded context owns this concept, and is the boundary drawn around language or deployment?",
        "Which terms are overloaded across contexts, and where is the translation (anti-corruption layer)?",
        "What are the aggregates, their invariants, and the transaction boundary? Does one transaction span aggregates?",
        "Are domain events the right integration mechanism, or is this a synchronous dependency?",
        "Does the model carry behavior, or is it an anemic data bag?",
    ], "Ubiquitous language is explicit, invariants are protected at the boundary, external models are translated."),
    ("Architecture & boundaries", [
        "Which direction do dependencies point? Can the core be tested without the framework, DB, or network?",
        "What is the smallest boundary that isolates this change (module, port, package)?",
        "What happens when each external dependency is slow, down, or returns garbage?",
        "Where does data ownership live, and is there a second writer?",
        "What is the operational story: config, migrations, rollout, rollback, observability?",
    ], "Policy depends on nothing; mechanisms are adapters; failure and migration paths are named."),
    ("Testable design", [
        "Where are the seams? Can time, randomness, IO, and external calls be injected?",
        "Which behaviors get fast unit tests, which need integration, which need contract tests?",
        "Does each acceptance criterion map to an observable check, or only to implementation details?",
        "Are the tests deterministic and independent (no shared state, no sleeps)?",
        "What is the failure signal when this decision turns out wrong in production?",
    ], "Behavior-first tests, deterministic seams, scenario-to-test traceability, a named failure signal."),
    ("Craftsmanship", [
        "Is this the smallest reversible step, or a big-bang change?",
        "Are names from the domain, or from the framework/table?",
        "Is the error model explicit (typed failures vs exceptions vs silent nulls)?",
        "Is there speculative abstraction (interfaces with one implementation, config nobody sets)?",
        "Is the migration path documented and rollback-able?",
    ], "Small steps, intention-revealing names, explicit errors, no speculative generality, documented migration."),
    ("Decision record", [
        "Are status, owner, and date recorded?",
        "Are consequences (positive and negative) written down?",
        "Is there a revisit trigger (metric, date, event)?",
        "Are links to evidence, code, and related ADRs present?",
    ], "A future reader can tell why, what was traded, and when to revisit."),
]

_TYPE_LENS_ADDITIONS = {
    "data": ("Domain fit (DDD)", "Which consistency guarantee is required, and which can be eventual?"),
    "api": ("Architecture & boundaries", "Who are the consumers, and what is the deprecation policy?"),
    "integration": ("Architecture & boundaries", "What is the failure isolation boundary and idempotency key?"),
    "security": ("Architecture & boundaries", "What is the blast radius if this control fails?"),
    "persistence": ("Domain fit (DDD)", "Does the repository boundary follow aggregate boundaries?"),
}


def _brief(parts, label, types, checks, readiness, signals, style, paths, root, focus):
    title = _title(parts["full"], "untitled decision")
    now = _now()
    out = [
        f"# Decision review brief — {title}",
        "",
        f"- Source: `{label}`",
        f"- Generated: {now}",
        f"- Detected type: {', '.join(types)}",
        f"- Readiness: **{readiness}** ({sum(1 for _, ok, _ in checks if ok)}/{len(checks)} record elements)",
        "- This brief is input to judgment, not a verdict. The agent fills the scorecard after reading the code.",
        "",
    ]
    if focus:
        out.insert(5, f"- Focus: {focus}")
    if any(not ok for _, ok, _ in checks):
        out.append("**Missing before this is reviewable:**")
        for name, ok, hint in checks:
            if not ok:
                out.append(f"- `{name}` — {hint}")
        out.append("")
    reversible = bool(_REVERSIBLE_RE.search(parts["full"]))
    out.append(
        f"**Reversibility:** {'stated' if reversible else 'not stated — one-way doors need more scrutiny'}"
    )
    if style:
        out.append(f"**Repo shape:** {style}")
    out.append("")
    if parts["alternatives"]:
        out.append("**Alternatives on record (verify they are credible, not strawmen):**")
        for alt in parts["alternatives"][:4]:
            out.append(f"- {alt}")
        out.append("")

    out += ["## Evidence signals (heuristic — verify before acting)", ""]
    out += [f"- {s}" for s in signals]
    if paths:
        out.append("")
        out.append("Inspected: " + ", ".join(f"`{_rel(root, p)}`" for p in paths))
    out.append("")

    moves = []
    for t in types:
        for m in _DESIGN_MOVES.get(t, []):
            if m not in moves:
                moves.append(m)
    moves += [
        "Invert a dependency so the unstable thing depends on the stable thing.",
        "Make an implicit boundary or invariant explicit before adding mechanism.",
        "Shrink the decision: can half of it ship independently and reversibly?",
    ]
    out += ["## Design moves to test", ""]
    out += [f"- {m}" for m in dict.fromkeys(moves)]
    out.append("")

    out += ["## Challenge questions", ""]
    lenses = list(_LENSES)
    if focus:
        key = focus.strip().lower()
        lenses.sort(key=lambda lens: 0 if key in lens[0].lower() else 1)
    for i, (name, questions, good) in enumerate(lenses, 1):
        out.append(f"### {i}. {name}")
        extra = next((q for t, (lens, q) in _TYPE_LENS_ADDITIONS.items()
                      if lens == name and t in types), "")
        for q in questions + ([extra] if extra else []):
            out.append(f"- {q}")
        out.append(f"**Good looks like:** {good}")
        out.append("")

    out += [
        "## Scorecard (agent fills; 1 = poor, 5 = strong, evidence required)",
        "",
        "| Lens | Score | Evidence (file:line, test, benchmark) | Action |",
        "|------|-------|----------------------------------------|--------|",
    ]
    for name, _, _ in _LENSES:
        out.append(f"| {name} | | | |")
    out += [
        "",
        "## Verdict (agent fills)",
        "",
        "```",
        "VERDICT: ACCEPT | REVISE | REVISIT | SPLIT",
        "STEELMAN: <the strongest version of the current decision>",
        "SMALLEST NEXT STEP: <the one change that most improves the design>",
        "REVISIT TRIGGER: <metric, date, or event that should reopen this>",
        "```",
        "",
        "Run the review with `/challenge-decision` and the `decision-challenger`",
        "subagent. It is advisory: it never blocks a gate or a merge.",
    ]
    return "\n".join(out) + "\n"


def _infer_root(root: Path, adr: str, spec_dir: str):
    """Return (root, adr, spec_dir), promoting the file's own git checkout.

    When the decision file lives inside a different git checkout than
    `repo_path` (e.g. `--adr=sources/<repo>/docs/x.md` run from the harness
    root), code-path signals must resolve against that checkout — not the
    harness root. Rewrites relative args to absolute paths so `_source`
    still finds them under the promoted root.
    """
    if not adr and not spec_dir:
        return root, adr, spec_dir
    target = Path(adr or spec_dir)
    p = target if target.is_absolute() else (
        root / target if (root / target).exists() else Path.cwd() / target
    )
    if spec_dir and adr == "":
        p = p / "SPEC.md"
    try:
        p = p.resolve()
    except OSError:
        return root, adr, spec_dir
    if not p.is_file():
        return root, adr, spec_dir
    for parent in (p.parent, *p.parents):
        if (parent / ".git").exists():
            if parent == root:
                return root, adr, spec_dir
            return parent, (str(p) if adr else adr), (str(p.parent) if spec_dir else spec_dir)
    return root, adr, spec_dir


@skill
def challenge_decision(
    repo_path: str = ".",
    spec_dir: str = "",
    adr: str = "",
    decision: str = "",
    paths: str = "",
    focus: str = "",
    write: bool = False,
    force: bool = False,
) -> str:
    """Review a design/architecture decision: completeness, design signals, challenge questions.

    Reads the decision from an ADR (`--adr`), a spec's `## Decisions` section
    (`--spec_dir`), or inline text (`--decision`). Emits a structured challenge
    brief: record completeness, heuristic code signals, design moves, and
    lens questions for architecture, DDD, testability, and craftsmanship.
    The agent fills the scorecard and verdict; this skill never judges design.
    Advisory — the verdict never blocks the delivery loop, but
    `spec_scaffold`'s G1 gate requires the review artifact
    (`DECISION-REVIEW.md`) before wave planning.

    Params:
      repo_path: Repository root (default ".").
      spec_dir: Feature dir containing SPEC.md; reads its `## Decisions`.
      adr: Path to an ADR/decision markdown file (relative to repo or absolute).
      decision: Inline decision text (use when there is no file yet).
      paths: Comma/space-separated repo-relative code paths to inspect for signals.
      focus: Bias the lens order (e.g. "ddd", "architecture", "testability", "craft").
      write: Write the brief to `<spec_dir>/DECISION-REVIEW.md` (or `<adr>-review.md`).
      force: Overwrite an existing review file.
    """
    root = Path(repo_path).resolve()
    if not root.is_dir():
        return f"ERROR: {repo_path} is not a directory"

    root, adr, spec_dir = _infer_root(root, adr, spec_dir)
    parts, label, write_dir, err = _source(root, spec_dir, adr, decision)
    if err:
        return err

    types = _detect_types(parts["full"])
    checks = _completeness(parts)
    readiness, _ = _readiness(checks, types)
    if readiness == "READY" and not _REVERSIBLE_RE.search(parts["full"]):
        readiness = "CHALLENGE"
    paths_found = _candidate_paths(root, paths, parts["full"])
    signals = _signals(root, paths_found)
    style = _style(root)

    brief = _brief(parts, label, types, checks, readiness,
                   signals, style, paths_found, root, focus)

    if not write:
        return brief

    if write_dir is None:
        return brief + (
            "\nERROR: --write needs --spec_dir or --adr to choose a destination"
        )
    target = write_dir / ("DECISION-REVIEW.md" if spec_dir else
                          f"{Path(adr).stem}-review.md")
    if target.exists() and not force:
        return brief + f"\nERROR: {_rel(root, target)} exists — pass --force to overwrite"
    target.write_text(brief)
    return brief + f"\nWrote {_rel(root, target)}"
