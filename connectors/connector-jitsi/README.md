# connector-jitsi (Meet)

This connector integrates Jitsi Meet as Prophet's Meet plane.

Jitsi is not an ACL database; Prophet must enforce join/host permissions by **token issuance**.

## Responsibilities
- Create meeting objects (Prophet canonical)
- Derive Jitsi room names deterministically from Prophet meeting IDs or Matrix room IDs
- Issue short-lived JWT join tokens (JOIN / HOST)
- Emit carriers:
  - MeetingCreated
  - JoinTokenIssued
  - MeetingParticipantJoined/Left (optional; requires event feed)

## TODO
- Decide meeting room naming scheme and collision rules
- Implement token minting policy and key rotation
- Optionally ingest conference events via Jitsi/Prosody hooks
