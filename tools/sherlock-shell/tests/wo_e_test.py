"""WO-E conformance — `python3 tests/wo_e_test.py` (no pytest).

A mock Synapse connector (drop-in for connectors/connector-synapse) + the real #39 mount table.
Teeth: a case room is provisioned per the runbook checklist with power levels PROJECTED from the mount
table and a §12 state card; room provisioning emits a receipted ProofArtifact (AC-1); a bot-power change
tracks the mount-table change (widening = Layer-2 review; narrowing = Layer-1 auto).
"""
from __future__ import annotations

import copy
import json
import os
import sys
import tempfile
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
TOOLS = os.path.dirname(PKG)
REPO = os.path.dirname(TOOLS)
sys.path.insert(0, PKG)
sys.path.insert(0, os.path.join(TOOLS, "proof-artifact-spine"))

from proof_artifact import verify_ledger  # noqa: E402
from publish import replay                 # noqa: E402
from room_controller import (              # noqa: E402
    Case, EnsureRoomRequest, EnsureRoomResponse, RoomController,
)

_passed = _failed = 0


def check(name, cond, detail=""):
    global _passed, _failed
    if cond:
        _passed += 1; print(f"  ok   {name}")
    else:
        _failed += 1; print(f"  FAIL {name} :: {detail}")


class MockSynapse:
    """Drop-in for SynapseConnector.ensure_room — records what it was asked to create."""
    def __init__(self):
        self.calls = []

    def ensure_room(self, req: EnsureRoomRequest) -> EnsureRoomResponse:
        self.calls.append(req)
        return EnsureRoomResponse(prophet_room_object_id=f"prophet-room:{req.alias}",
                                  matrix_room_id=f"!{abs(hash(req.alias)) % 10**8}:test")


def load_mount() -> dict:
    with open(os.path.join(REPO, "examples", "workspace-mount-table.example.json")) as f:
        return json.load(f)


def a_case() -> Case:
    return Case(case_id="c123", slug="baxter-shutdown", tenant="acme", severity="p1",
                owner="op:jordan", sla="4h", canonical_url="https://cases/c123", queue_space="#cases-p1")


def main() -> int:
    mount = load_mount()
    with tempfile.TemporaryDirectory() as d:
        led = Path(d) / "shell.jsonl"
        conn = MockSynapse()
        rc = RoomController(conn, led, server="example.com")

        prov = rc.provision_case_room(a_case(), mount)

        # room created via the connector, class=case, restricted join, alias per convention
        check("room provisioned via connector", len(conn.calls) == 1 and conn.calls[0].kind == "case")
        check("alias follows convention", prov.room.matrix_room_id.endswith(":test") and
              conn.calls[0].alias == "#case-c123-baxter-shutdown:example.com", conn.calls[0].alias)
        check("join rule restricted, directory off by default", conn.calls[0].join_rule == "restricted")

        # power levels projected from the mount table (runbook §4)
        pl = prov.power_levels
        check("bot=50, room_admin=100, invite>=moderator",
              pl["sherlock_bot"] == 50 and pl["room_admin"] == 100 and pl["invite"] == 50, str(pl))
        check("granting authorities carried from mounts", pl["granting_authorities"] == ["authority://sociosphere/grants"], str(pl["granting_authorities"]))

        # §12 state card
        card = prov.state_card
        for field in ("case_id", "severity", "owner", "sla_clock", "last_trace_id"):
            check(f"state card has {field}", field in card, str(card))
        check("state card last_trace_id = receipt hash", card["last_trace_id"] == prov.receipt["entryHash"])

        # AC-1: provisioning is a receipted publish
        check("provisioning receipted (seq 0)", prov.receipt["ledgerSeq"] == 0 and prov.receipt["recordType"] == "ProofArtifact")
        ok, msg = verify_ledger(led); check("shell ledger verifies", ok, msg)
        check("provisioning run package replays", replay(prov.receipt)["verified"])

        # runbook §4 binding: bot-power change tracks the mount-table change
        widened = copy.deepcopy(mount)
        widened["spec"]["entries"].append({"sourceId": "workspace-source:mail/inbox", "surface": "mail",
                                           "capabilities": ["read"], "grantedBy": "authority://x",
                                           "grantRef": "grant://y"})
        w = rc.authorize_power_change(mount, widened)
        check("widening power -> Layer 2 review, not auto-applied",
              w["layer"] == 2 and w["review_required"] and not w["apply"], str(w))
        n = rc.authorize_power_change(widened, mount)
        check("narrowing power -> Layer 1 auto-applied", n["layer"] == 1 and n["apply"], str(n))
        s = rc.authorize_power_change(mount, mount)
        check("no change -> auto (nothing to review)", s["apply"] and s["authority_change"] == "none")

    print(f"\n{_passed} passed, {_failed} failed")
    return 1 if _failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
