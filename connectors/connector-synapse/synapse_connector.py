"""Synapse connector skeleton.

This file is intentionally a scaffold. It defines the control-plane interface we expect
a Matrix/Synapse connector to implement for PFIS compliance.

Concrete implementation will depend on:
- Synapse deployment configuration (OIDC, closed federation, etc.)
- Application Service registration and event delivery
- Matrix Client-Server API usage for provisioning

We keep this in Python for reference; production connectors can be implemented in any language,
as long as they conform to PFIS/PPS/PAM and pass conformance.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

@dataclass(frozen=True)
class EnsureRoomRequest:
    org_id: str
    project_id: Optional[str]
    kind: str                # e.g., "general", "announcements"
    mode: str                # "secure"|"indexed"
    idempotency_key: str

@dataclass(frozen=True)
class EnsureRoomResponse:
    prophet_room_object_id: str
    matrix_room_id: str


class SynapseConnector:
    def __init__(self, *, synapse_base_url: str, as_token: str, hs_token: str) -> None:
        self.synapse_base_url = synapse_base_url
        self.as_token = as_token
        self.hs_token = hs_token

    # ---- control plane ----
    def ensure_room(self, req: EnsureRoomRequest) -> EnsureRoomResponse:
        """Idempotently ensure a Matrix room exists for the given scope/kind/mode.

        Must:
        - enforce Secure vs Indexed defaults
        - apply power levels derived from Prophet IAM
        - record engine mapping (prophet_object_id ↔ matrix_room_id)
        - emit ChatRoomEnsured carrier
        """
        raise NotImplementedError

    # ---- ingest plane ----
    def ingest_matrix_event(self, event: Dict[str, Any]) -> None:
        """Normalize a Matrix event into a workspace protocol pack Carrier.

        Must:
        - evaluate membrane policy
        - emit MembraneDecision carriers on deny/quarantine
        - emit ChatMessagePosted carriers for messages (indexed rooms → searchable)
        - attach frame_hash where applicable
        """
        raise NotImplementedError
