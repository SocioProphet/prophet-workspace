"""Sherlock Shell — Matrix room controller (WO-E of ADR-0001).

Realises the room-admin runbook (docs/ops/sherlock-shell-matrix-room-administration.md) as code:
rooms are the OPERATOR SURFACE of the workspace controller. A room's bot/actor power levels are a
*projection of the mount table*, not ad-hoc grants (runbook §4); every irreversible room action is a
receipted publish (runbook §10, AC-1); a case room is provisioned per the §6 checklist with the §12
state card.

Composes:
  - the Synapse connector (connectors/connector-synapse) — the Matrix seam, via its ensure_room() shape;
  - WO-C authority_change — widening bot power = mount widening = Layer 2 (review); narrowing = Layer 1;
  - WO-B publish(f_!) — room creation / power change emit a hash-chained ProofArtifact.

Verified with a mock connector (no live homeserver — G1 domain is bound later). The real SynapseConnector
is a drop-in: it implements the same ensure_room(EnsureRoomRequest)->EnsureRoomResponse.
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

_TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in ("proof-artifact-spine", "workspace-controller"):
    sys.path.insert(0, os.path.join(_TOOLS, _p))

from epistemic_ceiling import authority_change   # noqa: E402  (WO-C)
from proof_artifact import RunPackage             # noqa: E402  (WO-B)
from publish import PublishRequest, publish       # noqa: E402  (WO-B)

# runbook §4.2 baseline power levels
PL_DEFAULT_MEMBER = 0
PL_OPERATOR = 0
PL_BOT = 50
PL_MODERATOR = 50
PL_ROOM_ADMIN = 100


class Connector(Protocol):
    """The Matrix seam (matches connectors/connector-synapse SynapseConnector.ensure_room)."""
    def ensure_room(self, req: "EnsureRoomRequest") -> "EnsureRoomResponse": ...


@dataclass(frozen=True)
class EnsureRoomRequest:
    scope: str
    kind: str                 # runbook room class: control | queue | case | admin | bridge
    mode: str                 # encrypted | unencrypted (runbook §5)
    alias: str
    topic: str
    power_levels: dict
    history_visibility: str = "invited"
    join_rule: str = "restricted"   # runbook §7: prefer restricted / space-member


@dataclass
class EnsureRoomResponse:
    prophet_room_object_id: str
    matrix_room_id: str


@dataclass
class RoomProvision:
    room: EnsureRoomResponse
    state_card: dict
    power_levels: dict
    receipt: dict


def _power_levels_from_mount(mount_table: dict) -> dict:
    """Project the mount table into room power levels (runbook §4). The grant AUTHORITY on the mounts
    (grantedBy) is who administers; the workspace's own bot serves at PL_BOT; nothing off the table
    grants elevated power."""
    authorities = sorted({e["grantedBy"] for e in mount_table["spec"]["entries"]})
    return {
        "users_default": PL_DEFAULT_MEMBER,
        "events_default": PL_OPERATOR,
        "sherlock_bot": PL_BOT,
        "moderator": PL_MODERATOR,
        "room_admin": PL_ROOM_ADMIN,
        # restricted actions stay >= moderator (runbook §4.3)
        "invite": PL_MODERATOR, "kick": PL_MODERATOR, "ban": PL_MODERATOR, "redact": PL_MODERATOR,
        "state_default": PL_MODERATOR,
        "granting_authorities": authorities,
    }


def _alias(case_id: str, slug: str, server: str) -> str:
    return f"#case-{case_id}-{slug}:{server}"


@dataclass
class Case:
    case_id: str
    slug: str
    tenant: str
    severity: str
    owner: str
    sla: str
    canonical_url: str
    queue_space: str


def _state_card(case: Case, last_receipt_ref: str | None) -> dict:
    """runbook §12 — the card pinned in every case room."""
    return {
        "case_id": case.case_id, "tenant": case.tenant, "severity": case.severity,
        "status": "open", "owner": case.owner, "sla_clock": case.sla,
        "last_evidence_refresh": None, "linked_corpus_ids": [], "linked_ticket_ids": [],
        "latest_recommendation": None, "approval_requirements": "Layer-2 for mount widening",
        "last_trace_id": last_receipt_ref,   # the ProofArtifact of the last publish
    }


class RoomController:
    def __init__(self, connector: Connector, ledger: Path, server: str = "<server>"):
        self.connector = connector
        self.ledger = Path(ledger)
        self.server = server   # G1: homeserver domain bound later

    def provision_case_room(self, case: Case, mount_table: dict, *, external: bool = False,
                            mode: str = "unencrypted") -> RoomProvision:
        """runbook §6 checklist — provision a case room; power levels projected from the mount table;
        emit a receipt (room creation is an irreversible publish, AC-1)."""
        pl = _power_levels_from_mount(mount_table)
        alias = _alias(case.case_id, case.slug, self.server)
        topic = f"{case.canonical_url} | sev={case.severity} status=open owner={case.owner}"
        req = EnsureRoomRequest(scope=case.queue_space, kind="case", mode=mode, alias=alias,
                                topic=topic, power_levels=pl)
        room = self.connector.ensure_room(req)

        # receipt FIRST-CLASS: provisioning is a publish (f_!)
        receipt = publish(
            PublishRequest(
                agent="sherlock-shell", external=external,
                extent=mount_table["spec"]["declaredExtent"], phase="room-provision",
                epistemic_level="Derived", inputs=f"provision case room {case.case_id}",
                run=RunPackage(
                    plan=[f"class=case alias={alias}", f"power_levels bot={pl['sherlock_bot']}"],
                    tool_calls=[{"tool": "Synapse.ensure_room", "alias": alias, "kind": "case"}],
                    outputs=[{"matrix_room_id": room.matrix_room_id, "power_levels": pl}],
                    policy_report={"join_rule": req.join_rule, "history": req.history_visibility,
                                   "mode": mode}),
                cover=[e["sourceId"] for e in mount_table["spec"]["entries"]]),
            self.ledger)

        card = _state_card(case, last_receipt_ref=receipt["entryHash"])
        return RoomProvision(room=room, state_card=card, power_levels=pl, receipt=receipt)

    def authorize_power_change(self, prev_mount: dict, new_mount: dict) -> dict:
        """runbook §4 binding — a bot-power change tracks the mount-table change. Widening = Layer 2
        (review required before applying); narrowing/none = Layer 1 (auto)."""
        ac = authority_change(prev_mount, new_mount)
        return {"authority_change": ac.change, "layer": ac.layer,
                "review_required": ac.review_required, "added": ac.added, "removed": ac.removed,
                "apply": (not ac.review_required)}
