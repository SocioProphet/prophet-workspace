"""Grounded-assistant conformance — `python3 tests/grounded_assistant_test.py` (no pytest dep).

Teeth both ways (prophet-workspace#76 item 8, ADR-0001):
  PASS  a grounded answer (evidence + citation + confidence >= floor) emits a receipt and verifies;
  REJECT an ungrounded answer — no evidence refs;
  REJECT an ungrounded answer — no citations;
  REJECT confidence below the floor;
  REJECT a bot missing required client fields for its intent;
  REJECT (fail-closed, AC-1) when no receipt can be emitted — the answer is refused;
  the answer card carries the full Sherlock-Scout shape;
  bots.json and the BOTS registry agree, and all five named bots are present.
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

from assistant_bot import (  # noqa: E402
    BOTS,
    CONFIDENCE_FLOOR,
    AssistantRejected,
    DraftAnswerCard,
    answer,
)
from proof_artifact import verify_ledger  # noqa: E402  (from the consumed spine, via assistant_bot's sys.path)

_passed = _failed = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global _passed, _failed
    if cond:
        _passed += 1
        print(f"  ok   {name}")
    else:
        _failed += 1
        print(f"  FAIL {name} :: {detail}")


def grounded_draft(**over) -> DraftAnswerCard:
    base = dict(
        answer="Replace the pump seal kit (SK-204); torque to 12 Nm.",
        evidence=["evidence:parts-catalog:sk-204"],
        citations=["doc://parts/pump-x1.md#seal-kit"],
        freshness="fresh",
        confidence=0.82,
        missing_info=[],
        next_actions=["Order SK-204", "Book a technician if leak persists"],
    )
    base.update(over)
    return DraftAnswerCard(**base)


def main() -> int:
    with tempfile.TemporaryDirectory() as d:
        ledger = Path(d) / "spine.jsonl"
        parts = BOTS["parts-replacement"]
        client_ok = {"product_model": "Pump-X1", "part_id": "SK-204"}

        # PASS — grounded, receipted
        card = answer(parts, client_ok, grounded_draft(), ledger)
        check("grounded answer PASSES", card.receipt is not None)
        check("receipt is a ProofArtifact", card.receipt.get("recordType") == "ProofArtifact")
        check("receipt capped at Derived (external principal)",
              card.receipt.get("epistemicLevel") == "Derived")
        ok, msg = verify_ledger(ledger)
        check("receipt chain verifies", ok, msg)

        # answer card carries the full Sherlock-Scout shape
        shape = card.to_dict()
        need = {"answer", "evidence", "citations", "freshness", "confidence",
                "missingInfo", "nextActions", "receipt"}
        check("card has full scout shape", need <= set(shape), f"missing {need - set(shape)}")

        # REJECT — no evidence refs (ungrounded)
        try:
            answer(parts, client_ok, grounded_draft(evidence=[]), ledger)
            check("ungrounded (no evidence) REJECTED", False, "no raise")
        except AssistantRejected as e:
            check("ungrounded (no evidence) REJECTED", e.code == "ungrounded", e.code)

        # REJECT — no citations (ungrounded)
        try:
            answer(parts, client_ok, grounded_draft(citations=[]), ledger)
            check("ungrounded (no citation) REJECTED", False, "no raise")
        except AssistantRejected as e:
            check("ungrounded (no citation) REJECTED", e.code == "ungrounded", e.code)

        # REJECT — confidence below floor
        try:
            answer(parts, client_ok, grounded_draft(confidence=CONFIDENCE_FLOOR - 0.01), ledger)
            check("low-confidence REJECTED", False, "no raise")
        except AssistantRejected as e:
            check("low-confidence REJECTED", e.code == "low-confidence", e.code)

        # REJECT — bot missing required client fields for its intent
        try:
            answer(parts, {"product_model": "Pump-X1"}, grounded_draft(), ledger)
            check("missing client fields REJECTED", False, "no raise")
        except AssistantRejected as e:
            check("missing client fields REJECTED",
                  e.code == "missing-fields" and "part_id" in str(e), str(e))

        # count entries so far (each successful publish appends exactly one)
        entries = [l for l in ledger.read_text().splitlines() if l.strip()]
        check("only grounded answers reached the ledger", len(entries) == 1, f"{len(entries)} entries")

    # REJECT — fail-closed (AC-1): ledger unwritable -> no receipt -> answer refused, nothing published
    with tempfile.TemporaryDirectory() as d2:
        bad_ledger = Path(d2)  # a directory, not a file -> emit raises -> fail-closed
        try:
            answer(BOTS["parts-replacement"],
                   {"product_model": "Pump-X1", "part_id": "SK-204"},
                   grounded_draft(), bad_ledger)
            check("no-receipt fail-closed REJECTED", False, "no raise")
        except AssistantRejected as e:
            check("no-receipt fail-closed REJECTED", e.code == "receipt-required", e.code)

    # bots.json <-> registry agreement + all five named bots present
    bots_json = json.loads((Path(PKG) / "bots.json").read_text())
    json_ids = {b["id"] for b in bots_json["bots"]}
    reg_ids = {b.id for b in BOTS.values()}
    check("bots.json agrees with registry", json_ids == reg_ids, f"{json_ids ^ reg_ids}")
    check("all five named bots present", len(BOTS) == 5, str(sorted(BOTS)))
    check("required fields declared per bot",
          all(b.required_client_fields for b in BOTS.values()))

    print(f"\n{_passed} passed, {_failed} failed")
    return 1 if _failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
