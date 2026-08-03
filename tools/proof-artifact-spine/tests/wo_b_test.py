"""WO-B conformance — `python3 tests/wo_b_test.py` (no pytest dep).

Teeth both ways:
  - a publish emits a valid, hash-chained ProofArtifact; the chain verifies; the run package replays;
  - AC-1: a publish that CANNOT emit a receipt fails and nothing is published (fail-closed);
  - tamper anywhere breaks chain verification and replay;
  - external principals are capped at the Derived epistemic ceiling (STAR-1);
  - inclusion-exclusion nets out overlapping covers.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
sys.path.insert(0, PKG)

from proof_artifact import RunPackage, verify_ledger  # noqa: E402
from publish import PublishDenied, PublishRequest, publish, replay  # noqa: E402

_passed = _failed = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global _passed, _failed
    if cond:
        _passed += 1; print(f"  ok   {name}")
    else:
        _failed += 1; print(f"  FAIL {name} :: {detail}")


def mkreq(**over) -> PublishRequest:
    base = dict(agent="sherlock-scout", external=False, extent="cases/p1", phase="session-1",
                epistemic_level="Derived", inputs="Baxter shut down after Helene flooding.",
                run=RunPackage(plan=["retrieve", "ground", "answer"],
                               tool_calls=[{"tool": "Graph.QueryCypher", "args": {"lemma": "baxter"}}],
                               outputs=[{"answer": "flooding", "citations": ["edge:1"]}],
                               policy_report={"offline_first": True, "redaction": "strict"}),
                cover=["sec-a", "sec-b"], existing_covers=[])
    base.update(over)
    return PublishRequest(**base)


def main() -> int:
    with tempfile.TemporaryDirectory() as d:
        ledger = Path(d) / "spine.jsonl"

        # --- happy path: publish emits a chained receipt ---
        r0 = publish(mkreq(), ledger)
        check("publish emits ProofArtifact seq 0", r0["ledgerSeq"] == 0 and r0["recordType"] == "ProofArtifact")
        check("receipt carries DUAL input+output hashes (blake3 primary + sha256)",
              r0["inputHash"]["blake3"].startswith("blake3:") and r0["inputHash"]["sha256"].startswith("sha256:")
              and r0["outputHash"]["blake3"].startswith("blake3:") and r0["outputHash"]["sha256"].startswith("sha256:"))
        check("chain hash is BLAKE3 primary (Metadata Standards §3.2)", r0["entryHash"].startswith("blake3:"))
        check("receipt carries the three-time temporal model",
              all(k in r0["temporal"] for k in ("observed_at_micros", "txn_created", "uploaded_at_micros")))
        r1 = publish(mkreq(inputs="second fact"), ledger)
        check("second publish chains to first", r1["ledgerPrevHash"] == r0["entryHash"] and r1["ledgerSeq"] == 1)

        ok, msg = verify_ledger(ledger)
        check("chain verifies", ok, msg)

        # --- replay reconstructs + verifies ---
        rp = replay(r0)
        check("replay reconstructs plan/tool_calls/outputs", rp["verified"] and rp["plan"] == ["retrieve", "ground", "answer"])

        # --- AC-1: no receipt => no publish (unwritable ledger path is fail-closed) ---
        bad_ledger = Path(d) / "nope" / "deep" / "spine.jsonl"  # parent dir doesn't exist
        try:
            publish(mkreq(), bad_ledger)
            check("AC-1 fail-closed: publish w/o receipt is refused", False, "publish succeeded with no ledger")
        except PublishDenied as e:
            check("AC-1 fail-closed: publish w/o receipt is refused", e.code == "receipt-required", f"got {e.code}")
        check("AC-1: nothing written when receipt fails", not bad_ledger.exists())

        # --- tamper detection ---
        lines = ledger.read_text().splitlines()
        lines[0] = lines[0].replace("flooding", "sabotage")  # mutate an output inside seq 0
        ledger.write_text("\n".join(lines) + "\n")
        okt, msgt = verify_ledger(ledger)
        check("tamper breaks the chain", not okt, msgt)

        # --- epistemic ceiling: external principal cannot publish above Derived (STAR-1) ---
        ledger2 = Path(d) / "spine2.jsonl"
        try:
            publish(mkreq(external=True, epistemic_level="Proved"), ledger2)
            check("external principal capped at Derived", False, "external Proved publish allowed")
        except PublishDenied as e:
            check("external principal capped at Derived", e.code == "epistemic-ceiling", f"got {e.code}")
        # external at Derived is fine
        rext = publish(mkreq(external=True, epistemic_level="Derived"), ledger2)
        check("external at Derived permitted", rext["epistemicLevel"] == "Derived")

        # --- inclusion-exclusion on overlapping covers ---
        ledger3 = Path(d) / "spine3.jsonl"
        publish(mkreq(cover=["x", "y"]), ledger3)
        r_ovl = publish(mkreq(cover=["y", "z"], existing_covers=[["x", "y"]]), ledger3)
        incl = r_ovl["inclusionRecord"]
        check("inclusion-exclusion nets overlaps", incl["new_sections"] == ["z"] and incl["overlap_sections"] == ["y"] and incl["net_added"] == 1,
              f"got {incl}")

        # --- extent must be declared (FIB-1) ---
        try:
            publish(mkreq(extent=""), Path(d) / "spine4.jsonl")
            check("undeclared extent rejected", False, "empty extent allowed")
        except PublishDenied as e:
            check("undeclared extent rejected", e.code == "extent-undeclared", f"got {e.code}")

    print(f"\n{_passed} passed, {_failed} failed")
    return 1 if _failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
