# connector-synapse (Matrix/Synapse)

This connector is the **golden slice** candidate because it exercises:
- provisioning (org/project spaces + templated rooms)
- membership sync (Prophet IAM → Matrix membership)
- mode enforcement (Secure vs Indexed rooms)
- event ingestion (messages, reactions, membership changes) → Carriers
- receipts and membrane decisions
- indexing for indexed rooms

## TriRPC surfaces (shape)
- `prophet.chat.v1.EnsureOrgSpace_*`
- `prophet.chat.v1.EnsureProjectSpace_*`
- `prophet.chat.v1.EnsureRoom_*`
- `prophet.chat.v1.PostMessage_*`
- `prophet.chat.v1.IngestMatrixEvent_*`

Actual method/profile bindings live in `spec/prophet_workspace_spec/spec/MethodProfileBindings_v0.1.json`.

## Ingestion strategy
Preferred: Matrix Application Service (AS) event feed, plus a system bot identity for provisioning.
Guardrails: optional Synapse module for hard policy enforcement.

## TODO
- Implement AS registration generator
- Implement event normalizer → workspace protocol pack events (ChatMessagePosted, ChatRoomEnsured)
- Implement power-level mapping from Prophet roles (ADMIN/MOD/VIEW)
- Emit AclDowngrade carriers when a requested policy cannot be represented
