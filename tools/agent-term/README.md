# agent-term (WO-F) — the agent CLI / command palette + computer-use controller

The CLI face of the triRPC verbs and the safe computer-use controller. WO-F of
[ADR-0001](../../docs/adr/ADR-0001-open-agent-continuum.md). Ships in the SourceOS image behind the
validation gates (WO-G).

## Pieces

| File | Role |
|---|---|
| `aliases.py` | **`Alias.Resolve`** — the command palette (YubNub pattern, no legacy PHP): `g rain` → `Graph.QueryCypher`, `vm <cmd>` → `ComputerUse.Run`, `ask <q>` → Sherlock Scout. Unknown aliases rejected. |
| `controller.py` | The **computer-use controller**. Safety is structural: (1) **never the host** — actions run only in a **disposable guest VM**, a host target is refused before execution; (2) **Sentinel-gated** — offline-first blocks networked actions unless opted in; (3) **every action emits evidence** — a ProofArtifact (WO-B) with the action trace + evidence refs. |
| `cli.py` | `dispatch()` — resolve an alias and route it to the WO-A gateway or the controller. |

## Why the controller matters

Agent-S runs Python to control a computer. The contract makes that safe by construction: the controller
has **no code path that touches the host**; it only calls `run_in_disposable_vm`, and refuses any other
target. The disposable-VM executor is a `Protocol` with a fixture for conformance; the real Agent-S guest
runner is a drop-in.

## Verify

`python3 tests/wo_f_test.py` → **18/18**: alias resolution (+ unknown/missing rejected), host-target
refusal (nothing executed), disposable-VM run + evidence-bearing receipt + replay, offline-first block,
opt-in networked, and dispatch composing WO-A retrieval + the controller.

## Runtime follow-up (tracked, #43/#44)

Bind the real Agent-S disposable-VM guest runner (records screenshots/OCR/replay); ship agent-term in the
SourceOS image behind the WO-G promotion gates; route receipts through the shared `Ledger.Push`.
