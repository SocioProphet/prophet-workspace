"""Jitsi connector skeleton (token issuance as enforcement).

This module defines the control-plane expectations for integrating Jitsi Meet.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class CreateMeetingRequest:
    org_id: str
    project_id: Optional[str]
    room_object_id: Optional[str]  # Prophet chat room object (if created from chat)
    created_by_user_id: str
    idempotency_key: str

@dataclass(frozen=True)
class CreateMeetingResponse:
    meeting_object_id: str
    jitsi_room_name: str

@dataclass(frozen=True)
class IssueJoinTokenRequest:
    meeting_object_id: str
    user_id: str
    role: str  # "join"|"host"
    ttl_seconds: int

@dataclass(frozen=True)
class IssueJoinTokenResponse:
    jwt: str
    join_url: str


class JitsiConnector:
    def __init__(self, *, base_url: str, jwt_issuer: str, jwt_private_key_pem: str) -> None:
        self.base_url = base_url
        self.jwt_issuer = jwt_issuer
        self.jwt_private_key_pem = jwt_private_key_pem

    def create_meeting(self, req: CreateMeetingRequest) -> CreateMeetingResponse:
        """Idempotently create a meeting object and return deterministic room name."""
        raise NotImplementedError

    def issue_join_token(self, req: IssueJoinTokenRequest) -> IssueJoinTokenResponse:
        """Issue a short-lived JWT. Must emit JoinTokenIssued receipt carrier."""
        raise NotImplementedError
