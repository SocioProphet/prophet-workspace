# proof-artifact-spine (WO-B)

The **knowledge-publish arm** of the estate receipt spine. Every workspace `publish` (`f_!`) — write a
fact, close a case, promote a chunk, ship an image — emits a hash-chained **ProofArtifact** run package.
WO-B of [ADR-0001 — Open Agent Continuum](../../docs/adr/ADR-0001-open-agent-continuum.md).

The receipt-gateway already receipts *inference* publishes (`InferenceReceipt`, prophet-platform
#1233/#1237). This adds *knowledge* publishes on the **same ledger mechanics** (canonical JSON + sha256 +
`ledgerPrevHash` + `ledgerSeq`), so both record types live in one append-only, tamper-evident spine.

## The law it enforces

**AC-1 (the receipt law):** a publish that cannot emit a receipt is **not a publish**. `publish()` is
fail-closed — if ledger emission raises, the publish raises and nothing is considered published.

## Pieces

| File | Role |
|---|---|
| `proof_artifact.py` | `emit_proof_artifact()` (hash-chained append), `verify_ledger()` (chain + tamper check), `RunPackage`. |
| `publish.py` | `publish()` = `f_!`: epistemic ceiling (external ≤ `Derived`, STAR-1) → extent/phase gate → inclusion-exclusion on overlapping covers → **emit receipt (fail-closed)** → return. `replay()` reconstructs + re-verifies the run package. |
| `tests/wo_b_test.py` | 12 checks, teeth both ways. Run: `python3 tests/wo_b_test.py` → 12/12. |

## Record shape

A ProofArtifact carries: `recordType`, `ledgerSeq`, `ledgerPrevHash`, `emittedAt`, `extent`, `phase`,
`epistemicLevel`, `agent`, `inputHash`, `outputHash`, `runPackage` (plan / tool_calls / outputs /
policy_report), `inclusionRecord`, and the chaining `entryHash`.

## Runtime follow-up (tracked + assigned)

Productionising = routing emission through the shared ledger service behind the **`Ledger.Push`** triRPC
verb (ADR-0001), so the InferenceReceipt and ProofArtifact streams share one physical ledger, and
consolidating the emitter with `inference_receipt_emitter.py`. The mechanics here are byte-compatible with
that emitter by design. See the WO register / assigned issues.
