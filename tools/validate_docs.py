#!/usr/bin/env python3
"""Docs drift control (WO-I of ADR-0001) — Phase-4 lint for the Sherlock docs-as-code tree.

Enforces, over the MANAGED docs tree, the three anti-drift rules from docs/README.md:
  1. metadata — every page declares owner + status + a review/date field (the minimum-metadata standard);
  2. links   — every relative markdown link resolves to a real file (no dangling references);
  3. coverage — every continuum module (tools/<module>) has an owning doc page that names it,
     so no runtime object is undocumented (the "undocumented powers" anti-pattern).

Legacy top-level docs (outside the managed dirs) are reported as a warning count, not a failure, so the
gate can go green now and legacy docs are migrated deliberately (tracked). The checker EXCLUDES ITSELF and
its own test. Exit 0 clean; 1 on any violation (fail-closed).

Run: `python3 tools/validate_docs.py [repo_root]`
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

MANAGED_DIRS = ["adr", "ops", "architecture", "search", "agents", "cases", "evals",
                "security", "product", "reference"]
MANAGED_ROOT_FILES = ["README.md", "PROGRAM_GAPS_AND_OPEN_OBLIGATIONS.md"]

_OWNER = re.compile(r"(?im)^\s*[-*]?\s*\**owner\**\s*:", )
_STATUS = re.compile(r"(?im)^\s*[-*]?\s*\**status\**\s*:")
_REVIEW = re.compile(r"(?im)^\s*[-*]?\s*\**(last reviewed|date)\**\s*:")
_LINK = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


def managed_docs(docs: Path) -> list[Path]:
    out: list[Path] = []
    for d in MANAGED_DIRS:
        out += sorted((docs / d).rglob("*.md")) if (docs / d).is_dir() else []
    for f in MANAGED_ROOT_FILES:
        if (docs / f).is_file():
            out.append(docs / f)
    return out


def check_metadata(path: Path, text: str) -> list[str]:
    head = "\n".join(text.splitlines()[:15])   # header must be near the top
    missing = []
    if not _OWNER.search(head):
        missing.append("owner")
    if not _STATUS.search(head):
        missing.append("status")
    if not _REVIEW.search(head):
        missing.append("last-reviewed/date")
    return [f"{path}: missing metadata: {', '.join(missing)}"] if missing else []


def check_links(path: Path, text: str) -> list[str]:
    errs = []
    for target in _LINK.findall(text):
        t = target.split("#")[0].strip()
        if not t or t.startswith(("http://", "https://", "mailto:")):
            continue
        if not (path.parent / t).resolve().exists():
            errs.append(f"{path}: dangling link -> {target}")
    return errs


def check_coverage(repo: Path, docs: Path) -> list[str]:
    tools = repo / "tools"
    modules = [p.name for p in tools.iterdir()
               if p.is_dir() and (p / "README.md").exists() and p.name != "tests"] if tools.is_dir() else []
    corpus = "\n".join(f.read_text() for f in managed_docs(docs))
    return [f"coverage: continuum module {m!r} has no owning doc page (name it in the docs tree)"
            for m in modules if m not in corpus]


def main(argv: list[str]) -> int:
    repo = Path(argv[1]).resolve() if len(argv) > 1 else Path(__file__).resolve().parents[1]
    docs = repo / "docs"
    if not docs.is_dir():
        print(f"no docs/ under {repo}", file=sys.stderr)
        return 2

    self_paths = {Path(__file__).resolve(), (repo / "tools" / "tests" / "validate_docs_test.py").resolve()}
    problems: list[str] = []
    for md in managed_docs(docs):
        if md.resolve() in self_paths:
            continue
        text = md.read_text(encoding="utf-8")
        problems += check_metadata(md, text)
        problems += check_links(md, text)
    problems += check_coverage(repo, docs)

    # legacy docs outside the managed tree: warn-only (tracked migration)
    managed = {p.resolve() for p in managed_docs(docs)}
    legacy = [p for p in docs.rglob("*.md") if p.resolve() not in managed]

    if problems:
        print("DOCS DRIFT — violations:")
        for p in problems:
            print(f"  - {p}")
    print(f"\nchecked {len(managed)} managed docs; {len(legacy)} legacy docs (warn-only, migrate: WO-I)")
    print("OK: docs-as-code tree conforms" if not problems else f"FAIL: {len(problems)} violation(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
