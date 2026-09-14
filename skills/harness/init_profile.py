from pathlib import Path

from openharness.skill import skill


def _fmt_list(items):
    if not items:
        return "[]"
    return "[" + ", ".join(f'"{i}"' for i in items) + "]"


@skill
def init_profile(
    product: str,
    stage: str = "unset",
    repos: str = "",
    languages: str = "",
    frameworks: str = "",
    infra: str = "",
    ci: str = "unset",
    compliance: str = "",
    branch_prefix: str = "feat/",
    constraints: str = "",
    conventions: str = "",
    landmines: str = "",
    output_dir: str = ".",
) -> str:
    """Write draft REPOS.md and .openharness/ENV.md from user interview answers.

    Used by /init slash command. Comma-separated strings are split into
    lists; writes REPOS.md with one table row per comma-separated repo
    triple ("name:url:branch|stage"), ENV.md with frontmatter + section
    stubs. Prints paths written.

    Params:
      product: Product/ecosystem name.
      stage: greenfield | legacy-migration | modernization.
      repos: Comma-separated name:url:branch|stage triples.
      languages: Comma-separated language list.
      frameworks: Comma-separated framework list.
      infra: Comma-separated infra list.
      ci: CI system name.
      compliance: Comma-separated compliance list.
      branch_prefix: E.g. "feat/".
      constraints, conventions, landmines: Free-form section bodies.
      output_dir: Where to root the writes (default cwd).
    """
    out = Path(output_dir)
    (out / ".openharness").mkdir(parents=True, exist_ok=True)

    lang_list = [x.strip() for x in languages.split(",") if x.strip()]
    fw_list = [x.strip() for x in frameworks.split(",") if x.strip()]
    infra_list = [x.strip() for x in infra.split(",") if x.strip()]
    comp_list = [x.strip() for x in compliance.split(",") if x.strip()]

    env_text = f"""---
product: {product or 'UNSET'}
stage: {stage or 'unset'}
critical_flows: []
languages: {_fmt_list(lang_list)}
frameworks: {_fmt_list(fw_list)}
infra: {_fmt_list(infra_list)}
ci: {ci or 'unset'}
compliance: {_fmt_list(comp_list)}
branch_prefix: "{branch_prefix or 'feat/'}"
---
# Environment Profile
## Product
{product or '<filled by /init>'}
## Constraints
{constraints or '<filled by /init>'}
## Conventions
{conventions or '<filled by /init>'}
## Known Landmines
{landmines or '<filled by /init>'}
"""
    env_path = out / ".openharness" / "ENV.md"
    env_path.write_text(env_text)

    repo_rows: list[str] = []
    repo_names: list[str] = []
    repo_notes: list[str] = []
    for triple in (repos or "").split(","):
        triple = triple.strip()
        if not triple:
            continue
        parts = triple.split("|")
        meta = parts[0]
        stage_field = parts[1] if len(parts) > 1 else "unset"
        fields = meta.split(":")
        if len(fields) < 2:
            continue
        name = fields[0].strip()
        url = ":".join(fields[1:-1]).strip() if len(fields) > 2 else fields[1].strip()
        branch = fields[-1].strip() if len(fields) > 2 else "main"
        repo_names.append(name)
        repo_rows.append(f"| {name:<12s} | {url:<40s} | {branch:<6s} | {stage_field:<16s} |")
        repo_notes.append(f"### {name}\n- <role, stack, constraints, landmines — filled by /init>")

    repos_fm = "repos: " + _fmt_list(repo_names)
    repos_text = f"""---
{repos_fm}
---
# Managed Repositories

| name         | url                                      | branch | stage            |
|--------------|------------------------------------------|--------|------------------|
{chr(10).join(repo_rows) if repo_rows else ''}

## Per-repo notes
{chr(10).join(repo_notes) if repo_notes else ''}
"""
    repos_path = out / "REPOS.md"
    repos_path.write_text(repos_text)

    return f"Wrote:\n  - {repos_path}\n  - {env_path}"
