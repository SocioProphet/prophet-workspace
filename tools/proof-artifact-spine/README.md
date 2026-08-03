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
| `ledger_push.py` | **`Ledger.Push`** — the ONE physical append onto the spine. `ledger_push()` (the sole read-prev → seq → chain-hash → append primitive), the verb (`LedgerPushRequest` / `handle_ledger_push`), and `emit_inference_receipt()`. Every record type routes through here. |
| `ledger_push.proto` | triRPC IDL for the `Ledger.Push` verb. |
| `proof_artifact.py` | `emit_proof_artifact()` (shapes fields → `ledger_push`), `verify_ledger()` (chain + tamper check, record-type agnostic), `RunPackage`, and the FIPS chain primitives (`chain_hash`, `dual_hash`, `canonical`). |
| `custody_event.py` | 14-type `emit_custody_event()` (shapes fields → `ledger_push`). |
| `publish.py` | `publish()` = `f_!`: epistemic ceiling (external ≤ `Derived`, STAR-1) → extent/phase gate → inclusion-exclusion on overlapping covers → **emit receipt (fail-closed)** → return. `replay()` reconstructs + re-verifies the run package. |
| `tests/wo_b_test.py` | Teeth both ways. Run: `python3 tests/wo_b_test.py` → 14/14. |
| `tests/wo_b_ledger_push_test.py` | `Ledger.Push` consolidation: three record types on one ledger, one verify walk, byte-faithful refactor, fail-closed guards, cross-type tamper. Run: `python3 tests/wo_b_ledger_push_test.py` → 15/15. |

## Record shape

A ProofArtifact carries: `recordType`, `ledgerSeq`, `ledgerPrevHash`, `emittedAt`, `extent`, `phase`,
`epistemicLevel`, `agent`, `inputHash`, `outputHash`, `runPackage` (plan / tool_calls / outputs /
policy_report), `inclusionRecord`, and the chaining `entryHash`.

## `Ledger.Push` — one spine, one append verb (live)

ADR-0001 names a `Ledger.Push` verb as the productionisation of the spine. It exists now
(`ledger_push.py`): a single append primitive that owns read-prev → next `ledgerSeq` → FIPS SHA-256
`entryHash` → append. **ProofArtifact, InferenceReceipt, and CustodyEvent all route through it**, so they
share one physical, tamper-evident ledger that a single `verify_ledger` walk covers. The emitters became
thin field-shapers — the read-prev/seq/chain/append invariant is no longer copied three times.

Because `canonical()` sorts keys, routing an existing emitter through `Ledger.Push` yields
**byte-identical** entryHashes (the WO-B and MS-P4 suites stay green across the refactor — the
regression proof). The verb is fail-closed: an empty `record_type` or `fields` colliding with a
spine-owned key (`recordType` / `ledgerSeq` / `ledgerPrevHash` / `entryHash`) is rejected and nothing is
written. A network triRPC service is a thin transport over `handle_ledger_push` (`ledger_push.proto`).


## MS-P3 conformance (Metadata Standards v0.1)

Aligned to the metadata standard: content hashes are **dual** (`{sha256, blake3}`); the chain `entryHash` and the authoritative integrity assertion use **SHA-256 (FIPS 180-4)**; and every receipt carries the **three-time** `temporal` block (`observed_at_micros` / `txn_created` / `uploaded_at_micros`, §3.3). Requires the `blake3` package (`requirements.txt`). Verified: `python3 tests/wo_b_test.py` → 14/14.


## FIPS compliance + MS-P4 (14-type CustodyEvent)

**FIPS:** BLAKE3/BLAKE2b are NOT FIPS-validated, so the hash **chain** and the **authoritative** integrity assertion use **SHA-256** (FIPS 180-4). BLAKE3 is retained only as an *advisory/performance* fingerprint in the dual-hash — never for the chain or authoritative verification. (Supersedes MS-P3's BLAKE3 chain.)

**MS-P4** (`custody_event.py`): the full **14-type CustodyEvent** model (Metadata Standards §6.2) — Intake, HashVerification, ZonePromotion/Demotion, Examination, EnrichmentWrite, HypothesisLink, Read, ExportBundled, Disclosed, IntegrityViolation, PolicyException, ManualOverride, Retirement. Each declares its mandatory fields; emission is fail-closed. Events share the SAME FIPS chain as ProofArtifacts — one mixed, tamper-evident ledger. Verify: `python3 tests/wo_msp4_test.py` → 11/11.
