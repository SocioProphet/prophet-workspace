# sherlock-shell — Matrix room controller (WO-E)

Realises the [room-admin runbook](../../docs/ops/sherlock-shell-matrix-room-administration.md) as code:
Matrix rooms are the **operator surface of the workspace controller**. WO-E of
[ADR-0001](../../docs/adr/ADR-0001-open-agent-continuum.md).

## What it does

- **`provision_case_room()`** — the runbook §6 checklist: creates a case room via the Synapse connector
  (`connectors/connector-synapse` seam), with a canonical alias, restricted join, `#12` state card, and
  power levels **projected from the mount table** (§4) — nothing off the table grants elevated power.
- **`authorize_power_change()`** — the §4 binding: a bot-power change **tracks the mount-table change**
  via WO-C `authority_change` — widening = **Layer 2** (review required, not auto-applied); narrowing/none
  = **Layer 1** (auto).
- Every irreversible room action is a **receipted publish** (WO-B `publish`=`f_!`) — room provisioning
  emits a hash-chained, replayable ProofArtifact whose hash is pinned into the state card's `last_trace_id`
  (§10, AC-1).

## Composes

WO-C (`authority_change`, mount projection) + WO-B (`publish`, receipts) + the Synapse connector
(`ensure_room(EnsureRoomRequest)->EnsureRoomResponse`). Verified with a mock connector — the real
`SynapseConnector` is a drop-in.

## Verify

`python3 tests/wo_e_test.py` → **17/17**: room provisioned via connector, alias/join-rule per convention,
power levels projected from mounts, §12 state card complete, provisioning receipted + replays, and the
power-change Layer matrix (widen→L2 review, narrow→L1 auto).

## Runtime follow-up (tracked)

Bind the live `SynapseConnector` (homeserver domain = G1, bound later); wire `ingest_matrix_event` so room
messages route to Sherlock Scout (WO-D) and answers post back as evidence cards; route receipts through the
shared `Ledger.Push`. Semantics here are the contract those bindings honour.
