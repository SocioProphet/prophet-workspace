#!/usr/bin/env python3
"""Conformance validator for the GraphRAG grounded-answer-with-page-reference contract (pw#76).

Runs every answer fixture under fixtures/ through `grade_answer` and enforces teeth BOTH ways:
  - `*.valid.json`   MUST verdict VERIFY   (else the contract is too strict / a real answer is lost);
  - `*.invalid.json` MUST verdict REJECTED (else the guard has no teeth), and — when the fixture
    declares `reason_contains` — the rejection MUST cite that specific reason.

Annotation fixtures (`"kind": "annotation"`) are checked separately: the write plan conforms to the
HellGraph addNode contract and the provenance seal recomputes.

Exit 0 = all fixtures conform; 1 = conformance failure; 2 = usage error.
Run: `python3 validate_grounding.py [fixture.json ...]`   (stdlib-only, no pip)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from annotation_kg import annotation_to_kg, is_valid_write_node  # noqa: E402
from grounding import grade_answer  # noqa: E402
from proof_artifact import canonical, sha256  # noqa: E402  (via grounding's sys.path insert)

FIX = HERE / "fixtures"


def _grade_fixture(fx: dict) -> dict:
    return grade_answer(
        fx["answer"], fx["index"], fx["gold"],
        floor=fx.get("floor", 0.5), qa_floor=fx.get("qa_floor", 0.3),
    )


def _check_annotation(fx: dict) -> list[str]:
    errs: list[str] = []
    plan = annotation_to_kg(fx["annotation"])
    if not (plan["nodes"] and all(is_valid_write_node(n) for n in plan["nodes"])):
        errs.append("annotation: a node violates the HellGraph addNode(id, labels, props) contract")
    if not any("Annotation" in n["labels"] for n in plan["nodes"]):
        errs.append("annotation: no Annotation node emitted")
    if not any(e["rel"] == "ANNOTATES" for e in plan["edges"]):
        errs.append("annotation: no ANNOTATES edge emitted")
    seal = plan["provenance"]["seal"]
    # the seal must recompute deterministically over the sealed fields
    core = {k: fx["annotation"].get(k) for k in plan["provenance"]["sealed_fields"]}
    core["tags"] = sorted(fx["annotation"].get("tags") or [])
    if sha256(canonical(core)) != seal:
        errs.append("annotation: provenance seal does not recompute (not tamper-evident)")
    if plan["provenance"]["evidence_grade"] not in ("E1", "E2", "E3", "E4", "E5"):
        errs.append("annotation: evidence_grade outside E1..E5 vocabulary")
    return errs


def main(argv: list[str]) -> int:
    targets = [Path(a) for a in argv[1:]] or sorted(FIX.glob("*.json"))
    if not targets:
        print("no fixtures to validate", file=sys.stderr)
        return 2

    failures: list[str] = []
    for t in targets:
        fx = json.loads(t.read_text(encoding="utf-8"))

        if fx.get("kind") == "annotation":
            errs = _check_annotation(fx)
            if errs:
                failures += [f"{t.name}: {e}" for e in errs]
            else:
                print(f"  ok   {t.name} annotation → conformant sealed KG write plan")
            continue

        # The filename convention is load-bearing: *.valid.json ⇒ VERIFY, *.invalid.json ⇒ REJECTED.
        # A declared `expect` must AGREE with the filename, else the fixture author has silently
        # disarmed the guard — reject the fixture itself.
        by_name = "REJECTED" if t.name.endswith(".invalid.json") else "VERIFY"
        expect = fx.get("expect", by_name)
        if expect != by_name:
            failures.append(f"{t.name}: declared expect={expect} contradicts filename ({by_name})")
            continue

        verdict = _grade_fixture(fx)
        got = verdict["verdict"]

        if got != expect:
            detail = "; ".join(verdict["reasons"]) or "(no reasons)"
            failures.append(f"{t.name}: expected {expect} but got {got} :: {detail}")
            continue

        # negative fixtures must reject for the RIGHT reason when one is declared
        rc = fx.get("reason_contains")
        if expect == "REJECTED" and rc and not any(rc in r for r in verdict["reasons"]):
            failures.append(f"{t.name}: rejected, but not for '{rc}' :: {verdict['reasons']}")
            continue

        m = verdict["metrics"]
        tag = (f"rpa={m['retrieval_page_accuracy']:.3f} f1={m['qa_similarity_f1']:.3f} "
               f"refs={m['page_refs_resolved']}/{m['page_refs_total']}")
        if expect == "VERIFY":
            print(f"  ok   {t.name} VERIFY ({tag})")
        else:
            print(f"  ok   {t.name} correctly REJECTED ({verdict['reasons'][0][:64]}…)")

    if failures:
        print("\nGRAPHRAG GROUNDING CONFORMANCE FAILURES:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print(f"\nOK: {len(targets)} fixtures conform to the grounded-answer-with-page-reference contract")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
