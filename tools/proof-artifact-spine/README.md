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


## MS-P3 conformance (Metadata Standards v0.1)

Aligned to the metadata standard: content hashes are **dual** (`{sha256, blake3}`); the chain `entryHash` and the authoritative integrity assertion use **SHA-256 (FIPS 180-4)**; and every receipt carries the **three-time** `temporal` block (`observed_at_micros` / `txn_created` / `uploaded_at_micros`, §3.3). Requires the `blake3` package (`requirements.txt`). Verified: `python3 tests/wo_b_test.py` → 14/14.


## FIPS compliance + MS-P4 (14-type CustodyEvent)

**FIPS:** BLAKE3/BLAKE2b are NOT FIPS-validated, so the hash **chain** and the **authoritative** integrity assertion use **SHA-256** (FIPS 180-4). BLAKE3 is retained only as an *advisory/performance* fingerprint in the dual-hash — never for the chain or authoritative verification. (Supersedes MS-P3's BLAKE3 chain.)

**MS-P4** (`custody_event.py`): the full **14-type CustodyEvent** model (Metadata Standards §6.2) — Intake, HashVerification, ZonePromotion/Demotion, Examination, EnrichmentWrite, HypothesisLink, Read, ExportBundled, Disclosed, IntegrityViolation, PolicyException, ManualOverride, Retirement. Each declares its mandatory fields; emission is fail-closed. Events share the SAME FIPS chain as ProofArtifacts — one mixed, tamper-evident ledger. Verify: `python3 tests/wo_msp4_test.py` → 11/11.


## SEC-2 witness quorum (the promotion rule)

`witness_quorum.py`: a ProofArtifact is **promotable only when a k-of-N witness quorum (default 2-of-N) has independently signed it**. `promote()` is fail-closed — under quorum, a tampered artifact, an unrostered witness, or a forged signature all deny promotion. The quorum block is emitted onto the ProofArtifact under `witnessQuorum`, binding to the entry's `entryHash` (so it does not invalidate the chain).

**FIPS:** the eval named FROST — but **FROST/Schnorr-ed25519 is NOT FIPS-approved** and no FIPS-validated FROST lib is available in Python. So SEC-2 uses **independent per-witness ECDSA P-256 / SHA-256 signatures (FIPS 186-4/140-3-approvable) verified k-of-N** (a real multisig quorum, not an aggregated threshold sig), mirroring how BLAKE3 was made advisory above. Real crypto via `cryptography` (`requirements.txt`). FROST remains the advisory path (tracked). See [`docs/SEC-2-witness-quorum.md`](../../docs/SEC-2-witness-quorum.md). Verify: `python3 tests/sec2_test.py` → 11/11.

SEC-2 pairs with **SEC-1 Event-IR** (`schemas/sec-event-ir.schema.json`, `tools/validate_sec_event_ir.py`, [`docs/SEC-1-event-ir.md`](../../docs/SEC-1-event-ir.md)) — the normalized typed sensor event that feeds ProofArtifact claims.
