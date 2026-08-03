"""GraphRAG grounded-answer conformance — `python3 tests/grounding_test.py` (no pytest dep).

Teeth both ways, end to end:
  - the √2 fixture VERIFIES (page-refs resolve, accuracy ≥ floor, QA-F1 ≥ floor) and is RECEIPTED;
  - no-page-refs / unresolvable-ref / below-accuracy-floor / low-QA-F1 each REJECT for their reason;
  - every answer (VERIFY or REJECTED) emits a hash-chained ProofArtifact and the ledger verifies;
    tampering the ledger breaks verification (AC-1 has teeth);
  - the metric functions compute the documented values;
  - an annotation becomes a HellGraph-addNode-shaped, provenance-sealed KG write plan (no live write),
    and tampering the highlight changes the seal.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
sys.path.insert(0, PKG)

from annotation_kg import annotation_to_kg, is_valid_write_node  # noqa: E402
from grounding import answer_with_page_reference, grade_answer, verify_ledger  # noqa: E402
from metrics import qa_similarity_f1, retrieval_page_accuracy  # noqa: E402

FIX = Path(PKG) / "fixtures"
_passed = _failed = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global _passed, _failed
    if cond:
        _passed += 1; print(f"  ok   {name}")
    else:
        _failed += 1; print(f"  FAIL {name} :: {detail}")


def load(name: str) -> dict:
    return json.loads((FIX / name).read_text(encoding="utf-8"))


# ── metric units ─────────────────────────────────────────────────────────────
def test_metrics() -> None:
    a = ("hardy-wright", 40)
    b = ("hardy-wright", 41)
    c = ("hardy-wright", 100)
    check("rpa: all cited pages correct = 1.0", retrieval_page_accuracy({a, b}, {a, b}) == 1.0)
    check("rpa: 1 of 3 cited correct = 0.333", retrieval_page_accuracy({a, c, ("x", 1)}, {a, b}) == round(1 / 3, 6))
    check("rpa: no citations = 0.0", retrieval_page_accuracy(set(), {a}) == 0.0)
    check("qa_f1: identical = 1.0", qa_similarity_f1("√2 is irrational", "the √2 is irrational") == 1.0)
    check("qa_f1: disjoint = 0.0", qa_similarity_f1("bananas ripen", "√2 irrational proof") == 0.0)
    check("qa_f1: partial in (0,1)", 0.0 < qa_similarity_f1("√2 is irrational by parity", "√2 is irrational") < 1.0)


# ── verdict teeth via grade_answer ───────────────────────────────────────────
def test_verdicts() -> None:
    v = load("sqrt2-irrationality.valid.json")
    r = grade_answer(v["answer"], v["index"], v["gold"], floor=v["floor"], qa_floor=v["qa_floor"])
    check("√2 fixture VERIFIES", r["verdict"] == "VERIFY", str(r["reasons"]))
    check("√2 rpa == 1.0", r["metrics"]["retrieval_page_accuracy"] == 1.0)
    check("√2 qa_f1 above floor", r["metrics"]["qa_similarity_f1"] >= v["qa_floor"])

    for fn, needle in [
        ("no-page-references.invalid.json", "no page references"),
        ("unresolvable-page-reference.invalid.json", "unresolvable page references"),
        ("below-accuracy-floor.invalid.json", "retrieval_page_accuracy"),
        ("low-qa-f1.invalid.json", "qa_similarity_f1"),
    ]:
        fx = load(fn)
        rr = grade_answer(fx["answer"], fx["index"], fx["gold"], floor=fx["floor"], qa_floor=fx["qa_floor"])
        check(f"{fn} REJECTED", rr["verdict"] == "REJECTED", str(rr))
        check(f"{fn} rejected for '{needle}'", any(needle in x for x in rr["reasons"]), str(rr["reasons"]))


# ── receipt teeth (every answer receipted; chain verifies; tamper breaks it) ──
def test_receipts() -> None:
    with tempfile.TemporaryDirectory() as d:
        ledger = Path(d) / "grounding.ledger.jsonl"

        v = load("sqrt2-irrationality.valid.json")
        out1 = answer_with_page_reference(v["answer"], v["index"], v["gold"], ledger=ledger,
                                          floor=v["floor"], qa_floor=v["qa_floor"])
        check("VERIFY answer is receipted", out1["receipt"]["recordType"] == "ProofArtifact")
        check("VERIFY answer epistemic_level=Derived", out1["answer"]["epistemic_level"] == "Derived")
        check("receipt records the verdict", out1["receipt"]["runPackage"]["policy_report"]["verdict"] == "VERIFY")

        bad = load("no-page-references.invalid.json")
        out2 = answer_with_page_reference(bad["answer"], bad["index"], bad["gold"], ledger=ledger,
                                          floor=bad["floor"], qa_floor=bad["qa_floor"])
        check("REJECTED answer STILL receipted", out2["receipt"]["recordType"] == "ProofArtifact")
        check("REJECTED answer clamped to Speculative", out2["answer"]["epistemic_level"] == "Speculative")

        ok, msg = verify_ledger(ledger)
        check("ledger chain verifies after 2 receipts", ok, msg)
        check("chain has 2 entries", "2 entries" in msg, msg)

        # tamper: flip a byte in the ledger, chain must break
        lines = ledger.read_text(encoding="utf-8").splitlines()
        lines[0] = lines[0].replace("VERIFY", "FORGED", 1)
        ledger.write_text("\n".join(lines) + "\n", encoding="utf-8")
        ok2, _ = verify_ledger(ledger)
        check("tampered ledger fails verification", not ok2)


# ── annotation → KG write plan (no live write) ───────────────────────────────
def test_annotation_kg() -> None:
    fx = load("annotation-highlight.valid.json")
    plan = annotation_to_kg(fx["annotation"])
    check("all nodes match addNode(id,labels,props)", all(is_valid_write_node(n) for n in plan["nodes"]))
    labels = {tuple(n["labels"])[0] for n in plan["nodes"]}
    check("emits Annotation + Document + Tag nodes", {"Annotation", "Document", "Tag"} <= labels, str(labels))
    rels = {e["rel"] for e in plan["edges"]}
    check("emits ANNOTATES + TAGGED edges", {"ANNOTATES", "TAGGED"} <= rels, str(rels))
    check("provenance seal present + sha256", plan["provenance"]["seal"].startswith("sha256:"))
    check("evidence_grade in E1..E5", plan["provenance"]["evidence_grade"] in ("E1", "E2", "E3", "E4", "E5"))

    # tamper-evidence: changing the highlighted text changes the seal
    tampered = json.loads(json.dumps(fx["annotation"]))
    tampered["highlighted_text"] = "There IS a rational whose square is 2."
    seal2 = annotation_to_kg(tampered)["provenance"]["seal"]
    check("editing highlight changes the seal", seal2 != plan["provenance"]["seal"])

    # order-independent over tags (seal stable under tag reordering)
    reordered = json.loads(json.dumps(fx["annotation"]))
    reordered["tags"] = list(reversed(reordered["tags"]))
    check("seal stable under tag reordering",
          annotation_to_kg(reordered)["provenance"]["seal"] == plan["provenance"]["seal"])


def main() -> int:
    print("GraphRAG grounded-answer-with-page-reference — conformance")
    test_metrics()
    test_verdicts()
    test_receipts()
    test_annotation_kg()
    print(f"\n{_passed} passed, {_failed} failed")
    return 1 if _failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
