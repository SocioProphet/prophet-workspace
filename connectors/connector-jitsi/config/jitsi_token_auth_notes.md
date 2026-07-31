# Token auth notes (placeholder)

We configure Jitsi's Prosody to require JWT tokens.
Prophet/connector issues:
- `aud=jitsi`
- `sub=user:<uuid>`
- `room=<canonical_room_name>`
- role claims (host/moderator)

This connector is responsible for minting tokens and recording receipts.
