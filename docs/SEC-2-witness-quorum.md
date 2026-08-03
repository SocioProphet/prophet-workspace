# SEC-2 — Witness Quorum (the ProofArtifact promotion rule)

A ProofArtifact (WO-B, `tools/proof-artifact-spine/proof_artifact.py`) is a hash-chained,
self-consistent claim. SEC-2 adds the immune system's **promotion rule**: a claim is only
promotable once a **k-of-N witness quorum** (default **2-of-N**) has independently signed it.
The quorum block is emitted onto the ProofArtifact under `witnessQuorum`.

Eval: prophet-workspace#62 (SEC-2).

## FIPS decision (the important one)

The eval named **FROST 2-of-N**. On verification:

- **FROST / Schnorr threshold signatures over ed25519 are NOT FIPS-approved.** ed25519/EdDSA
  is FIPS 186-5, but FROST's threshold construction is not a FIPS-validated scheme.
- **No FIPS-validated FROST implementation is available in Python.** The only crypto library
  present in the environment is `cryptography` (46.0.5); there is no `frost` / `pynacl`.

So SEC-2 does **not** use FROST. The quorum is realized as **independent per-witness FIPS
ECDSA signatures over NIST P-256 with SHA-256** (FIPS 186-4; P-256 + SHA-256 are FIPS 140-3
approvable), verified against a **k-of-N policy**. This is a genuine multisig quorum — N
distinct signatures, k required — **not** an aggregated threshold signature. It is larger on
the wire and verifies k signatures instead of one, but it is FIPS-clean and needs no trusted
distributed-key-generation ceremony.

This mirrors the estate's existing pattern (`compute-gateway`/`mcp-a2a-zero-trust`
`quorum_proof.schema.json`: independent signatures + a rule) rather than inventing a new
primitive, and it mirrors how the spine made **BLAKE3 advisory**: the FIPS posture travels
*with the artifact* (the required `fips_posture` field) and the non-FIPS path is named, not
silently used.

| Path | Status |
|---|---|
| `ecdsa-p256-quorum` (this module) — ECDSA P-256 / SHA-256, k-of-N | **FIPS-approved. Default. Real crypto (via `cryptography`), not mocked.** |
| FROST-ed25519 aggregated threshold sig — smaller block, single verify | **Advisory / aspirational. NOT used.** Pending a FIPS-validated implementation — tracked as a blocker issue assigned @mdheller. |

## Block shape (`schemas/sec-witness-quorum.schema.json`)

```
{ schema_version, scheme:"ecdsa-p256-quorum",
  threshold:{k,n},
  committed:{record_type:"ProofArtifact", entry_hash:"sha256:…"},   # what was witnessed
  signed_payload_hash:"sha256:…",                                    # sha256(canonical(committed))
  roster:[{witness_id, alg:"ECDSA_P256_SHA256", public_key_spki_b64}],   # N enrolled public keys
  signatures:[{witness_id, sig_b64}],                                # collected witness sigs
  fips_posture:"…" }
```

Witnesses sign `canonical(committed)` — i.e. they sign the **entryHash** of the specific
ledger entry. Because the quorum binds *back* to the already-computed `entryHash`, attaching
the block does not invalidate the hash chain (the chain hashes the pre-quorum body).

## Guarantees / teeth

Structural + lockstep: `tools/validate_sec_witness_quorum.py` (scheme pinned to
`ecdsa-p256-quorum`; posture required; bound to a ProofArtifact; strict shape;
schema⇄validator lockstep). 1 example, 4 invalid rejected.

Cryptographic, fail-closed (real ECDSA): `tools/proof-artifact-spine/tests/sec2_test.py` — 11 checks:
- 2-of-3 quorum verifies and promotes;
- under quorum (1 of 2) is **refused** (`promote()` raises `PromotionDenied`);
- the block does not verify against a *different* ProofArtifact (tamper);
- a signature from an **unrostered** witness is refused;
- duplicate signatures from one witness **count once** (cannot fake quorum);
- a forged signature is rejected;
- `signed_payload_hash` binds to `canonical(committed)`;
- scheme is `ecdsa-p256-quorum` and the posture names FROST as not-FIPS-approved / not used.

## API

`witness_quorum.py`: `Witness.generate(id)`, `build_quorum_block(receipt, roster, signers, k=2)`,
`verify_quorum(receipt, block) -> (ok, msg)`, `attach_quorum(receipt, block)`,
`promote(receipt, block, k=None)` (fail-closed gate).
