# metadata-intake (MS-P2)

The **canonical metadata-record at intake** — GAP-1 of the Metadata Standards adoption. Closes the
"fragmented receipts, no single record per artifact" gap: the moment an artifact enters the platform it
acquires the one identity+integrity+temporal+provenance+classification record (metadata-standards v0.1),
and an **Intake CustodyEvent** is emitted through the receipt spine (WO-B).

## What it does
`intake(content_bytes, …)`:
1. Computes the hash **first**, over raw bytes (NIST SP 800-86): BLAKE3-256 primary + SHA-256 (FRE 902(14)).
2. Builds the canonical record (identity/integrity/temporal three-time/provenance/classification).
3. Validates it against the **vendored** `schemas/metadata-record.schema.json` (from `SocioProphet/metadata-standards`) **+** the cross-field teeth (E3+ ⇒ null_hypotheses; E5 ⇒ counter_explanations; hash-first).
4. Emits an **Intake CustodyEvent** (fail-closed, AC-1) — hash-chained, bound to the artifact's BLAKE3, carrying the record in its run package.

`mount` (f*) then restricts a workspace to a set of these records; `publish` (f_!) emits further CustodyEvents referencing `artifact_id`.

## Verify
`python3 tests/wo_msp2_test.py` → **14/14** (schema conformance, hashes match recompute, hash-first, chained+replayable Intake event, non-conformant intakes refused-before-recording).

## Provenance
`schemas/metadata-record.schema.json` is vendored verbatim from `SocioProphet/metadata-standards`; re-vendor on standard changes. Requires `blake3` (`requirements.txt`).
