"""MS-P4 conformance — `python3 tools/proof-artifact-spine/tests/wo_msp4_test.py` (no pytest).

Teeth: each of the 14 CustodyEvent types emits with valid fields and chains (FIPS SHA-256); an event
missing a mandatory field, a bad actor_type/zone/custody_status, and an IntegrityViolation without the
matching status are all REJECTED before writing; a MIXED ledger (ProofArtifact publishes + CustodyEvents)
verifies end to end; the chain hash is SHA-256 (FIPS), never blake3.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
sys.path.insert(0, PKG)

from custody_event import EVENT_TYPES, CustodyEventError, emit_custody_event  # noqa: E402
from proof_artifact import RunPackage, emit_proof_artifact, verify_ledger      # noqa: E402

_passed = _failed = 0


def check(name, cond, detail=""):
    global _passed, _failed
    if cond:
        _passed += 1; print(f"  ok   {name}")
    else:
        _failed += 1; print(f"  FAIL {name} :: {detail}")


# valid mandatory-field kwargs per event type
VALID = {
    "Intake": dict(hash_at_event="sha256:ab", zone_to="Landing"),
    "HashVerification": dict(hash_at_event="sha256:ab", custody_status="Intact"),
    "ZonePromotion": dict(zone_from="Landing", zone_to="Examination", tool_name="exodus-examine-v0.1"),
    "ZoneDemotion": dict(zone_from="Examination", zone_to="Landing", note="re-examination needed"),
    "Examination": dict(tool_name="parser-v1", hash_at_event="sha256:ab"),
    "EnrichmentWrite": dict(tool_name="enricher-v1"),
    "HypothesisLink": dict(hypothesis_ids=["H-1"]),
    "Read": dict(),
    "ExportBundled": dict(hash_at_event="sha256:ab", trpc_commit_receipt="beacon:xyz"),
    "Disclosed": dict(recipient_id="counsel@example", trpc_commit_receipt="beacon:xyz"),
    "IntegrityViolation": dict(hash_at_event="sha256:ab", note="mismatch", custody_status="IntegrityViolation"),
    "PolicyException": dict(zone_from="Landing", zone_to="Governed", note="gate not met, override sought"),
    "ManualOverride": dict(note="analyst override, justification attached"),
    "Retirement": dict(note="logically retired, hash preserved"),
}


def main() -> int:
    check("all 14 standard event types covered", set(VALID) == set(EVENT_TYPES) and len(EVENT_TYPES) == 14,
          f"{sorted(set(EVENT_TYPES)-set(VALID))}")

    with tempfile.TemporaryDirectory() as d:
        led = Path(d) / "custody.jsonl"
        # emit one of every type in sequence → all chain
        for i, (et, kw) in enumerate(VALID.items()):
            ev = emit_custody_event(led, event_type=et, artifact_id="AF-0042",
                                    actor_id="op:jordan", actor_type="HumanUser", **kw)
            if i == 0:
                check("event chain hash is SHA-256 (FIPS)", ev["entryHash"].startswith("sha256:"), ev["entryHash"][:12])
        ok, msg = verify_ledger(led)
        check("14-event custody chain verifies", ok, msg)
        n = sum(1 for _ in open(led)); check("14 events written", n == 14, f"n={n}")

        # mixed ledger: interleave a ProofArtifact publish then another custody event → still verifies
        emit_proof_artifact(led, extent="corpus/x", phase="publish", epistemic_level="Derived",
                            agent="scout", inputs="x", run=RunPackage(plan=["p"]))
        emit_custody_event(led, event_type="Read", artifact_id="AF-0042", actor_id="a", actor_type="AIAgent")
        okm, msgm = verify_ledger(led)
        check("MIXED ProofArtifact + CustodyEvent ledger verifies", okm, msgm)

        # teeth: missing mandatory field rejected
        try:
            emit_custody_event(led, event_type="ZonePromotion", artifact_id="a", actor_id="a",
                               actor_type="HumanUser", zone_from="Landing")  # missing zone_to + tool_name
            check("missing mandatory field rejected", False)
        except CustodyEventError as e:
            check("missing mandatory field rejected", e.code == "missing-mandatory", e.code)
        # bad actor_type
        try:
            emit_custody_event(led, event_type="Read", artifact_id="a", actor_id="a", actor_type="Wizard")
            check("bad actor_type rejected", False)
        except CustodyEventError as e:
            check("bad actor_type rejected", e.code == "bad-actor-type", e.code)
        # bad zone
        try:
            emit_custody_event(led, event_type="ZonePromotion", artifact_id="a", actor_id="a",
                               actor_type="HumanUser", zone_from="Landing", zone_to="Atlantis", tool_name="t")
            check("bad zone rejected", False)
        except CustodyEventError as e:
            check("bad zone rejected", e.code == "bad-zone", e.code)
        # unknown event type
        try:
            emit_custody_event(led, event_type="Teleport", artifact_id="a", actor_id="a", actor_type="HumanUser")
            check("unknown event type rejected", False)
        except CustodyEventError as e:
            check("unknown event type rejected", e.code == "unknown-event-type", e.code)
        # IntegrityViolation must carry the matching status
        try:
            emit_custody_event(led, event_type="IntegrityViolation", artifact_id="a", actor_id="a",
                               actor_type="VerificationProcess", hash_at_event="sha256:ab", note="x",
                               custody_status="Intact")
            check("IntegrityViolation status-mismatch rejected", False)
        except CustodyEventError as e:
            check("IntegrityViolation status-mismatch rejected", e.code == "status-mismatch", e.code)

        # a rejected emit wrote nothing (ledger still 16: 14 + publish + read)
        okf, _ = verify_ledger(led); nf = sum(1 for _ in open(led))
        check("rejected emits recorded nothing", okf and nf == 16, f"n={nf}")

    print(f"\n{_passed} passed, {_failed} failed")
    return 1 if _failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
