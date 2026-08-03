"""WO-B Ledger.Push conformance — `python3 tests/wo_b_ledger_push_test.py` (no pytest dep).

Proves the consolidation ADR-0001 names: InferenceReceipt + ProofArtifact (+ CustodyEvent) share ONE
physical ledger through ONE append verb.

Teeth both ways:
  - three record types append to one file, seqs monotonic across types, chain links hold, one
    verify_ledger walk covers the mixed chain;
  - the refactor is byte-faithful: routing an emitter through Ledger.Push produces the SAME entryHash
    as building the body directly (regression proof for the existing suites);
  - the verb rejects spine-owned keys and empty record_type (fail-closed);
  - tamper on ANY record type (incl. an InferenceReceipt) breaks the mixed chain.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
sys.path.insert(0, PKG)

from custody_event import emit_custody_event  # noqa: E402
from ledger_push import (  # noqa: E402
    LedgerPushError, LedgerPushRequest, emit_inference_receipt, handle_ledger_push, ledger_push,
)
from proof_artifact import (  # noqa: E402
    GENESIS_PREV, RunPackage, canonical, chain_hash, emit_proof_artifact, verify_ledger,
)

_passed = _failed = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global _passed, _failed
    if cond:
        _passed += 1; print(f"  ok   {name}")
    else:
        _failed += 1; print(f"  FAIL {name} :: {detail}")


def run() -> RunPackage:
    return RunPackage(plan=["retrieve", "answer"], tool_calls=[{"tool": "Graph.QueryCypher"}],
                      outputs=[{"answer": "flooding"}], policy_report={"offline_first": True})


def main() -> int:
    with tempfile.TemporaryDirectory() as d:
        ledger = Path(d) / "spine.jsonl"

        # --- three record types onto ONE physical ledger, interleaved ---
        pa = emit_proof_artifact(ledger, extent="cases/p1", phase="s1", epistemic_level="Derived",
                                 agent="sherlock-scout", inputs="Baxter shut down after Helene.", run=run())
        ir = emit_inference_receipt(ledger, kind="embedding", actor="noetica-impair",
                                    inputs="Baxter shut down after Helene.", outputs="[0.1,0.2,0.3]")
        ce = emit_custody_event(ledger, event_type="Read", artifact_id="AF-1", actor_id="u1",
                                actor_type="HumanUser")
        pa2 = emit_proof_artifact(ledger, extent="cases/p1", phase="s2", epistemic_level="Derived",
                                  agent="sherlock-scout", inputs="second fact", run=run())

        check("ProofArtifact is seq 0", pa["ledgerSeq"] == 0 and pa["recordType"] == "ProofArtifact")
        check("InferenceReceipt is seq 1 on the SAME ledger", ir["ledgerSeq"] == 1 and ir["recordType"] == "InferenceReceipt")
        check("CustodyEvent is seq 2 on the SAME ledger", ce["ledgerSeq"] == 2 and ce["recordType"] == "CustodyEvent")
        check("chain links across record types", ir["ledgerPrevHash"] == pa["entryHash"]
              and ce["ledgerPrevHash"] == ir["entryHash"] and pa2["ledgerPrevHash"] == ce["entryHash"])
        check("InferenceReceipt is dual-hashed (SHA-256 authoritative + BLAKE3 advisory)",
              ir["inputHash"]["sha256"].startswith("sha256:") and ir["inputHash"]["blake3"].startswith("blake3:"))

        # --- one verify walk covers the mixed chain ---
        ok, msg = verify_ledger(ledger)
        check("mixed-type chain verifies in one walk", ok, msg)
        check("four entries total", "4 entries" in msg, msg)

        # --- the verb surface produces the same entry as the function ---
        resp = handle_ledger_push(LedgerPushRequest(record_type="InferenceReceipt",
                                  fields={"kind": "completion", "actor": "a"}), ledger)
        check("Ledger.Push verb appends seq 4", resp.ledger_seq == 4)
        ok2, _ = verify_ledger(ledger)
        check("chain still verifies after verb append", ok2)

    # --- byte-faithful refactor: ledger_push body == a hand-built body (regression proof) ---
    with tempfile.TemporaryDirectory() as d:
        led = Path(d) / "one.jsonl"
        entry = ledger_push(led, record_type="X", fields={"b": 2, "a": 1})
        # rebuild the body exactly as the primitive would and recompute the hash independently
        body = {"recordType": "X", "ledgerSeq": 0, "ledgerPrevHash": GENESIS_PREV, "b": 2, "a": 1}
        expect = chain_hash(GENESIS_PREV + canonical(body))
        check("entryHash is prevHash+canonical(body), key-order independent", entry["entryHash"] == expect,
              f"{entry['entryHash']} != {expect}")

    # --- fail-closed: reserved keys and empty record_type rejected; nothing written ---
    with tempfile.TemporaryDirectory() as d:
        led = Path(d) / "guard.jsonl"
        for name, kwargs in [
            ("rejects spine-owned key in fields", dict(record_type="X", fields={"ledgerSeq": 9})),
            ("rejects entryHash in fields", dict(record_type="X", fields={"entryHash": "x"})),
            ("rejects empty record_type", dict(record_type="", fields={})),
        ]:
            try:
                ledger_push(led, error_cls=LedgerPushError, **kwargs)
                check(name, False, "expected LedgerPushError")
            except LedgerPushError:
                check(name, True)
        check("nothing written on rejected pushes", not led.exists())

    # --- tamper on an InferenceReceipt breaks the mixed chain ---
    with tempfile.TemporaryDirectory() as d:
        led = Path(d) / "tamper.jsonl"
        emit_proof_artifact(led, extent="e", phase="p", epistemic_level="Derived", agent="a",
                            inputs="x", run=run())
        emit_inference_receipt(led, kind="embedding", actor="a", inputs="x", outputs="[1]")
        lines = led.read_text().splitlines()
        lines[1] = lines[1].replace('"embedding"', '"completion"')  # mutate the InferenceReceipt
        led.write_text("\n".join(lines) + "\n")
        okt, msgt = verify_ledger(led)
        check("tamper on InferenceReceipt breaks the chain", not okt, msgt)

    print(f"\n{_passed} passed, {_failed} failed")
    return 1 if _failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
