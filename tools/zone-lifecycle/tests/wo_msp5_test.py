"""MS-P5 conformance — `python3 tools/zone-lifecycle/tests/wo_msp5_test.py` (no pytest).

Teeth: an artifact promotes Discovery→Diamond ONLY as gates are met, one zone at a time, each emitting a
ZonePromotion CustodyEvent (FIPS chain); a promotion whose gate is unmet is refused (fail-closed) and
recorded as a PolicyException; demotion to a lower zone is permitted; retirement is the only terminal
(hash preserved, no destroy path); one owning zone throughout; the whole custody ledger verifies.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
TOOLS = os.path.dirname(PKG)
sys.path.insert(0, PKG)
sys.path.insert(0, os.path.join(TOOLS, "proof-artifact-spine"))

from proof_artifact import verify_ledger  # noqa: E402
from zone_lifecycle import ArtifactZoneState, ZoneDenied, demote, promote, retire  # noqa: E402

_passed = _failed = 0


def check(name, cond, detail=""):
    global _passed, _failed
    if cond:
        _passed += 1; print(f"  ok   {name}")
    else:
        _failed += 1; print(f"  FAIL {name} :: {detail}")


def ready_state() -> ArtifactZoneState:
    return ArtifactZoneState(
        artifact_id="AF-0042", owning_zone="Discovery",
        intake_done=True, hashes_computed=True, identity_complete=True,
        evidence_grade="E4", counter_explanations=["benign MDM"], classification_complete=True,
        analyst_signoff=True, forensic_bundle_signed=True, disclosure_authorized=True,
        recipient_id="counsel@example")


def actor():
    return dict(actor_id="op:jordan", actor_type="HumanUser")


def main() -> int:
    with tempfile.TemporaryDirectory() as d:
        led = Path(d) / "custody.jsonl"

        # --- full gated promotion Discovery -> Diamond, one step at a time ---
        s = ready_state()
        path = []
        for _ in range(5):
            ev = promote(s, ledger=led, **actor())
            path.append((ev["fields"]["zone_from"], ev["fields"]["zone_to"]))
        check("promoted Discovery->Diamond via 5 gated steps",
              s.owning_zone == "Diamond" and path == [("Discovery","Landing"),("Landing","Examination"),
              ("Examination","Integration"),("Integration","Governed"),("Governed","Diamond")], str(path))
        check("at Diamond, further promotion refused", _raises(lambda: promote(s, ledger=led, **actor()), "at-top"))
        ok, msg = verify_ledger(led); check("promotion custody chain verifies", ok, msg)

        # --- gate not met -> PolicyException recorded + fail-closed ---
        led2 = Path(d) / "c2.jsonl"
        s2 = ArtifactZoneState(artifact_id="AF-0043", owning_zone="Examination",
                               evidence_grade="E2", classification_complete=False)  # fails E3 gate
        check("promotion with unmet gate refused", _raises(lambda: promote(s2, ledger=led2, **actor()), "gate-not-met"))
        check("owning zone unchanged after refused promotion", s2.owning_zone == "Examination")
        # the refusal was recorded as a PolicyException
        import json
        evs = [json.loads(l) for l in open(led2)]
        check("refused promotion recorded as PolicyException",
              len(evs) == 1 and evs[0]["eventType"] == "PolicyException" and evs[0]["fields"]["zone_to"] == "Integration")
        ok2, _ = verify_ledger(led2); check("policy-exception ledger verifies", ok2)

        # --- demotion permitted ---
        led3 = Path(d) / "c3.jsonl"
        s3 = ready_state(); s3.owning_zone = "Governed"
        dv = demote(s3, to_zone="Examination", note="re-examination", ledger=led3, **actor())
        check("demotion to lower zone permitted", s3.owning_zone == "Examination" and dv["eventType"] == "ZoneDemotion")
        check("'demotion' upward is refused", _raises(lambda: demote(s3, to_zone="Diamond", note="x", ledger=led3, **actor()), "not-a-demotion"))

        # --- retirement is the only terminal; hash preserved, no destroy path ---
        led4 = Path(d) / "c4.jsonl"
        s4 = ready_state(); s4.owning_zone = "Governed"
        rv = retire(s4, note="logically retired", ledger=led4, **actor())
        check("retirement emits Retirement event, sets retired", rv["eventType"] == "Retirement" and s4.retired)
        check("retired artifact cannot be promoted (still exists, hash preserved)",
              _raises(lambda: promote(s4, ledger=led4, **actor()), "retired"))
        import zone_lifecycle
        check("no destroy/delete API exists (destruction forbidden)",
              not any(hasattr(zone_lifecycle, n) for n in ("destroy", "delete", "purge")))

        # --- one owning zone invariant (single scalar, moved not copied) ---
        s5 = ready_state()
        promote(s5, ledger=Path(d) / "c5.jsonl", **actor())
        check("one owning zone (moved, not multiplied)", isinstance(s5.owning_zone, str) and s5.owning_zone == "Landing")

    print(f"\n{_passed} passed, {_failed} failed")
    return 1 if _failed else 0


def _raises(fn, code: str) -> bool:
    try:
        fn(); return False
    except ZoneDenied as e:
        return e.code == code


if __name__ == "__main__":
    raise SystemExit(main())
