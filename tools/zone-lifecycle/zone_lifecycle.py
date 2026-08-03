"""WNZL Dirt-to-Diamond zone lifecycle (MS-P5, Metadata Standards §5).

Every artifact has exactly ONE owning zone at a time. Promotion up the ordered path is gated by policy
assessment (fail-closed); demotion to a lower zone is permitted; **destruction is forbidden** — the only
terminal is Retirement, which preserves the hash. Every transition emits a CustodyEvent (MS-P4) onto the
FIPS-approved receipt spine, so the zone history is tamper-evident and replayable.

    Discovery(0) → Landing(1) → Examination(2) → Integration(3) → Governed(4) → Diamond(5)

Zone entry gates (§5.1):
  Discovery→Landing      : complete intake re-processing (intake_done)
  Landing→Examination    : intake CustodyEvent + hashes computed + identity block complete
  Examination→Integration: evidence_grade >= E3 AND counter_explanations present AND classification complete
  Integration→Governed   : analyst sign-off (+ legal review flag honoured if applicable)
  Governed→Diamond       : ForensicBundle signed + disclosure authorised + recipient identified
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "proof-artifact-spine"))
from custody_event import emit_custody_event  # noqa: E402  (MS-P4)

ZONES = ["Discovery", "Landing", "Examination", "Integration", "Governed", "Diamond"]
_RANK = {z: i for i, z in enumerate(ZONES)}
_GRADE = {"E1": 1, "E2": 2, "E3": 3, "E4": 4, "E5": 5}


class ZoneDenied(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


@dataclass
class ArtifactZoneState:
    """The ONE owning zone + the facts the promotion gates read. Referencing zones are separate and
    unlimited; only this owning zone may take state-modifying enrichments (§5 fundamental rule)."""
    artifact_id: str
    owning_zone: str = "Discovery"
    retired: bool = False
    # gate facts
    intake_done: bool = False
    hashes_computed: bool = False
    identity_complete: bool = False
    evidence_grade: str = "E1"
    counter_explanations: list = field(default_factory=list)
    classification_complete: bool = False
    analyst_signoff: bool = False
    legal_review_required: bool = False
    legal_review_done: bool = False
    forensic_bundle_signed: bool = False
    disclosure_authorized: bool = False
    recipient_id: str | None = None


def _gate(frm: str, to: str, s: ArtifactZoneState) -> tuple[bool, str]:
    if (frm, to) == ("Discovery", "Landing"):
        return (s.intake_done, "intake re-processing not complete")
    if (frm, to) == ("Landing", "Examination"):
        ok = s.intake_done and s.hashes_computed and s.identity_complete
        return (ok, "need intake event + hashes + identity block")
    if (frm, to) == ("Examination", "Integration"):
        ok = _GRADE.get(s.evidence_grade, 0) >= 3 and bool(s.counter_explanations) and s.classification_complete
        return (ok, "need evidence_grade>=E3 + counter_explanations + classification complete")
    if (frm, to) == ("Integration", "Governed"):
        ok = s.analyst_signoff and (s.legal_review_done or not s.legal_review_required)
        return (ok, "need analyst sign-off (+ legal review if required)")
    if (frm, to) == ("Governed", "Diamond"):
        ok = s.forensic_bundle_signed and s.disclosure_authorized and bool(s.recipient_id)
        return (ok, "need signed ForensicBundle + disclosure authorization + recipient")
    return (False, f"no gate defined for {frm}->{to}")


def promote(state: ArtifactZoneState, *, actor_id: str, actor_type: str, ledger: Path,
            tool_name: str = "zone-controller") -> dict:
    """Promote by exactly ONE zone up the ordered path if the gate passes. Emits a ZonePromotion
    CustodyEvent (fail-closed). On a failed gate emits a PolicyException event and raises."""
    if state.retired:
        raise ZoneDenied("retired", "a retired artifact cannot be promoted")
    cur = state.owning_zone
    idx = _RANK[cur]
    if idx >= _RANK["Diamond"]:
        raise ZoneDenied("at-top", "already in Diamond; no further promotion")
    target = ZONES[idx + 1]
    ok, reason = _gate(cur, target, state)
    if not ok:
        # record the refused promotion as a PolicyException (auditable), then fail-closed
        emit_custody_event(Path(ledger), event_type="PolicyException", artifact_id=state.artifact_id,
                           actor_id=actor_id, actor_type=actor_type,
                           zone_from=cur, zone_to=target, note=f"gate not met: {reason}")
        raise ZoneDenied("gate-not-met", f"{cur}->{target}: {reason}")
    ev = emit_custody_event(Path(ledger), event_type="ZonePromotion", artifact_id=state.artifact_id,
                            actor_id=actor_id, actor_type=actor_type,
                            zone_from=cur, zone_to=target, tool_name=tool_name)
    state.owning_zone = target   # ONE owning zone — moved, not copied
    return ev


def demote(state: ArtifactZoneState, *, to_zone: str, note: str, actor_id: str, actor_type: str,
           ledger: Path) -> dict:
    """Demote to a LOWER zone (permitted). Emits a ZoneDemotion CustodyEvent with a reason."""
    if state.retired:
        raise ZoneDenied("retired", "a retired artifact cannot be demoted")
    if to_zone not in _RANK:
        raise ZoneDenied("bad-zone", to_zone)
    if _RANK[to_zone] >= _RANK[state.owning_zone]:
        raise ZoneDenied("not-a-demotion", f"{to_zone} is not below {state.owning_zone}")
    ev = emit_custody_event(Path(ledger), event_type="ZoneDemotion", artifact_id=state.artifact_id,
                            actor_id=actor_id, actor_type=actor_type,
                            zone_from=state.owning_zone, zone_to=to_zone, note=note)
    state.owning_zone = to_zone
    return ev


def retire(state: ArtifactZoneState, *, note: str, actor_id: str, actor_type: str, ledger: Path) -> dict:
    """Logical retirement — the ONLY terminal. The artifact and its hash are PRESERVED; there is no
    destroy path (§5: destruction is not permitted)."""
    ev = emit_custody_event(Path(ledger), event_type="Retirement", artifact_id=state.artifact_id,
                            actor_id=actor_id, actor_type=actor_type, note=note)
    state.retired = True
    return ev
