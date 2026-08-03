"""WO-I conformance for the docs drift-control lint — `python3 tools/tests/validate_docs_test.py`.

Teeth both ways against synthetic repos: a compliant tree passes (exit 0); a missing-metadata page, a
dangling link, and an uncovered module each fail (exit 1). Confirms the checker excludes itself.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
sys.path.insert(0, TOOLS)

import validate_docs as vd  # noqa: E402

_passed = _failed = 0


def check(name, cond, detail=""):
    global _passed, _failed
    if cond:
        _passed += 1; print(f"  ok   {name}")
    else:
        _failed += 1; print(f"  FAIL {name} :: {detail}")


META = ("- **Owner:** @mdheller\n- **Status:** active\n- **Last reviewed:** 2026-08-03\n\n")


def build_repo(root: Path, *, good_meta=True, dangling=False, module_covered=True):
    docs = root / "docs"; (docs / "adr").mkdir(parents=True); (docs / "architecture").mkdir()
    (root / "tools" / "widget").mkdir(parents=True)
    (root / "tools" / "widget" / "README.md").write_text("# widget\n")
    adr = "# ADR\n" + (META if good_meta else "") + \
          ("See [x](./missing.md)\n" if dangling else "See [self](./ADR.md)\n")
    (docs / "adr" / "ADR.md").write_text(adr)
    comp = "# components\n" + META + ("names widget module\n" if module_covered else "nothing\n")
    (docs / "architecture" / "components.md").write_text(comp)
    (docs / "README.md").write_text("# index\n" + META)


def run(root: Path) -> int:
    return vd.main(["validate_docs.py", str(root)])


def main() -> int:
    with tempfile.TemporaryDirectory() as d:
        r = Path(d) / "good"; build_repo(r)
        check("compliant tree passes (exit 0)", run(r) == 0)

        r2 = Path(d) / "nometa"; build_repo(r2, good_meta=False)
        check("missing metadata fails (exit 1)", run(r2) == 1)

        r3 = Path(d) / "dangling"; build_repo(r3, dangling=True)
        check("dangling link fails (exit 1)", run(r3) == 1)

        r4 = Path(d) / "uncovered"; build_repo(r4, module_covered=False)
        check("uncovered module fails (exit 1)", run(r4) == 1)

        # coverage error is ACTIONABLE: names the offending module + the exact one-line fix, and is
        # still fail-closed on a genuinely-unnamed module (prophet-workspace#76; motivated by #77/#89/#97).
        r5 = Path(d) / "actionable"
        (r5 / "tools" / "widgetron").mkdir(parents=True)
        (r5 / "tools" / "widgetron" / "README.md").write_text("# widgetron\n")
        arch = r5 / "docs" / "architecture"; arch.mkdir(parents=True)
        (arch / "continuum-modules.md").write_text("# component map\n" + META + "no module named here\n")
        errs = vd.check_coverage(r5, r5 / "docs")
        msg = "\n".join(errs)
        check("coverage flags the uncovered module", len(errs) == 1)
        check("coverage message names the offending module", "widgetron" in msg)
        check("coverage message points to the fix file", "docs/architecture/continuum-modules.md" in msg)
        check("coverage message gives the exact fix (FIX:)", "FIX:" in msg)
        check("coverage still fail-closed on unnamed module (exit 1)", run(r5) == 1)

        # unit: metadata + link checks directly
        errs = vd.check_metadata(Path("x.md"), "# t\nno header here\n")
        check("check_metadata flags owner/status/date", len(errs) == 1 and "owner" in errs[0])
        ok = vd.check_metadata(Path("x.md"), "# t\n" + META)
        check("check_metadata passes a good header", ok == [])

        # self-exclusion: the checker file itself is never scanned as a managed doc
        check("checker excludes itself", vd.Path(vd.__file__).name == "validate_docs.py")

    print(f"\n{_passed} passed, {_failed} failed")
    return 1 if _failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
