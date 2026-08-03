"""SEC-2 conformance — `python3 tests/sec2_test.py` (no pytest dep).

Cryptographic teeth both ways, over REAL ECDSA P-256 signatures (no mock crypto):
  - a 2-of-N quorum verifies and promotes a ProofArtifact;
  - the promotion rule is fail-closed: under quorum (1 of 2) is REFUSED;
  - a tampered ProofArtifact (entryHash changed) breaks the quorum (committed no longer binds);
  - a signature from an unrostered witness is refused (fail-closed);
  - duplicate signatures from ONE witness count once (cannot fake quorum);
  - a forged signature is rejected;
  - the emitted block binds signed_payload_hash to canonical(committed);
  - FIPS posture: scheme is ecdsa-p256-quorum and the posture string states FROST is NOT used.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
sys.path.insert(0, PKG)

from proof_artifact import RunPackage, canonical, sha256  # noqa: E402
from publish import PublishRequest, publish  # noqa: E402
from witness_quorum import (  # noqa: E402
    SCHEME, Witness, PromotionDenied, build_quorum_block, promote, verify_quorum,
)

_passed = _failed = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global _passed, _failed
    if cond:
        _passed += 1; print(f"  ok   {name}")
    else:
        _failed += 1; print(f"  FAIL {name} :: {detail}")


def mkreceipt(ledger: Path, inputs: str = "Baxter shut down after Helene flooding.") -> dict:
    req = PublishRequest(
        agent="sherlock-scout", external=False, extent="cases/p1", phase="session-1",
        epistemic_level="Derived", inputs=inputs,
        run=RunPackage(plan=["retrieve", "ground"], tool_calls=[],
                       outputs=[{"answer": "flooding"}], policy_report={}))
    return publish(req, ledger)


def main() -> int:
    with tempfile.TemporaryDirectory() as d:
        ledger = Path(d) / "spine.jsonl"
        receipt = mkreceipt(ledger)
        roster = [Witness.generate("witness-a"), Witness.generate("witness-b"), Witness.generate("witness-c")]

        # --- happy path: 2-of-3 quorum verifies + promotes ---
        block = build_quorum_block(receipt, roster, signers=roster[:2], k=2)
        ok, msg = verify_quorum(receipt, block)
        check("2-of-3 quorum verifies", ok, msg)
        check("scheme is FIPS ecdsa-p256-quorum (not FROST)", block["scheme"] == SCHEME)
        posture = block["fips_posture"].lower()
        check("fips_posture states FROST not FIPS-approved", "not fips-approved" in posture and "frost" in posture)
        promoted = promote(receipt, block, k=2)
        check("promotion attaches witnessQuorum block", promoted.get("witnessQuorum") == block)
        check("signed_payload_hash binds to canonical(committed)",
              block["signed_payload_hash"] == sha256(canonical({"record_type": "ProofArtifact", "entry_hash": receipt["entryHash"]})))

        # --- fail-closed: under quorum (1 of 2 required) is refused ---
        under = build_quorum_block(receipt, roster, signers=roster[:1], k=2)
        oku, msgu = verify_quorum(receipt, under)
        check("under-quorum (1<2) verify fails", not oku, msgu)
        try:
            promote(receipt, under, k=2)
            check("under-quorum promotion refused", False, "promotion succeeded under quorum")
        except PromotionDenied as e:
            check("under-quorum promotion refused", e.code == "quorum-required", f"got {e.code}")

        # --- tamper: change the ProofArtifact the block was built for ---
        other = mkreceipt(Path(d) / "spine2.jsonl", inputs="a different fact")
        okt, msgt = verify_quorum(other, block)  # block committed to `receipt`, verify against `other`
        check("quorum does not verify against a different ProofArtifact", not okt, msgt)

        # --- unrostered witness signature is refused (fail-closed) ---
        outsider = Witness.generate("witness-x")
        block_outsider = build_quorum_block(receipt, roster, signers=[roster[0]], k=2)
        # graft a real, valid signature from a witness NOT on the roster
        payload = canonical({"record_type": "ProofArtifact", "entry_hash": receipt["entryHash"]}).encode()
        block_outsider["signatures"].append(outsider.sign(payload))
        oko, msgo = verify_quorum(receipt, block_outsider)
        check("unrostered witness signature refused", not oko, msgo)

        # --- duplicate signatures from ONE witness count once (cannot fake quorum) ---
        dup = build_quorum_block(receipt, roster, signers=[roster[0]], k=2)
        dup["signatures"].append(dict(dup["signatures"][0]))  # same witness twice
        okd, msgd = verify_quorum(receipt, dup)
        check("duplicate witness counts once (still under quorum)", not okd, msgd)

        # --- forged signature is rejected ---
        forged = build_quorum_block(receipt, roster, signers=roster[:2], k=2)
        forged["signatures"][0]["sig_b64"] = "MEUCIQD" + "A" * 80 + "=="  # garbage but base64-ish
        okf, msgf = verify_quorum(receipt, forged)
        check("forged signature rejected", not okf, msgf)

    print(f"\n{_passed} passed, {_failed} failed")
    return 1 if _failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
