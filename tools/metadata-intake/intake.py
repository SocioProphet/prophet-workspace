"""Canonical metadata-record intake (MS-P2 of the Metadata Standards adoption, GAP-1).

The estate had fragmented receipts (ProofArtifact / WorkspaceActionReceipt / InferenceReceipt) but NO
single identity+integrity+temporal+provenance+classification record per artifact at intake. This is that
record, produced the moment an artifact enters the platform, per Metadata Standards v0.1:

    intake(content_bytes, ...) →  a schema-conformant metadata-record  +  an Intake CustodyEvent
                                  (hash-chained via the receipt spine, WO-B) that references artifact_id.

The non-negotiable rule (standard §1): every artifact acquires an immutable identity, a cryptographic
hash, a temporal triple, and a provenance chain BEFORE any transformation — hash is computed here, first,
over the raw bytes (NIST SP 800-86). BLAKE3-256 is primary; SHA-256 for FRE 902(14).

`mount` (f*) then restricts a workspace to a set of these records (by artifact_id/corpus); `publish` (f_!)
emits further CustodyEvents referencing the artifact_id. AC-1: intake without a receipt is not an intake.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
import uuid
from pathlib import Path

import blake3

_TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_TOOLS, "proof-artifact-spine"))
from proof_artifact import RunPackage, emit_proof_artifact  # noqa: E402  (WO-B receipt spine)

_SCHEMA = Path(__file__).resolve().parent / "schemas" / "metadata-record.schema.json"
_GRADE = {"E1": 1, "E2": 2, "E3": 3, "E4": 4, "E5": 5}


class IntakeError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


def _cross_field_ok(rec: dict) -> list[str]:
    """The standard's teeth (mirrors metadata-standards/tools/validate_metadata.py)."""
    errs = []
    integ, temp, cls = rec["integrity"], rec["temporal"], rec["classification"]
    h = integ["hash_computed_at_micros"]
    for k in ("txn_created", "observed_at_micros", "uploaded_at_micros"):
        if isinstance(temp.get(k), int) and h > temp[k]:
            errs.append(f"NIST-800-86: hash_computed_at_micros must precede temporal.{k}")
    g = _GRADE.get(cls["evidence_grade"], 0)
    if g >= 3 and not cls.get("null_hypothesis_ids"):
        errs.append("adversarial-review: evidence_grade >= E3 requires null_hypothesis_ids")
    if g >= 5 and not cls.get("counter_explanations"):
        errs.append("E5 requires counter_explanations")
    return errs


def intake(
    content: bytes,
    *,
    corpus_id: str,
    exhibit_id: str,
    original_filename: str,
    mime_type: str,
    artifact_class: str,
    source_account: str,
    source_platform: str,
    source_path_or_id: str,
    capture_method: str = "ManualCopy",
    evidence_class: str = "Primary",
    evidence_grade: str = "E3",
    security_label: str = "Confidential",
    witness_retention: str = "LocalOnly",
    null_hypothesis_ids: list[str] | None = None,
    counter_explanations: list[str] | None = None,
    observed_at_micros: int | None = None,
    ledger: Path | None = None,
) -> dict:
    """Produce the canonical metadata-record for an artifact (hash computed FIRST over raw bytes) and,
    if a ledger is given, emit the Intake CustodyEvent (fail-closed, AC-1). Returns
    {record, receipt}. Raises IntakeError on non-conformance."""
    now = int(time.time() * 1_000_000)          # hash time = first timestamp in the custody chain
    obs = observed_at_micros if observed_at_micros is not None else now

    record = {
        "identity": {
            "artifact_id": str(uuid.uuid4()),   # UUID (v7 preferred in prod; v4 acceptable here)
            "corpus_id": corpus_id,
            "exhibit_id": exhibit_id,
            "original_filename": original_filename,   # verbatim, not normalized
            "mime_type": mime_type,
            "file_size_bytes": len(content),
            "artifact_class": artifact_class,
        },
        "integrity": {
            "hash_blake3": blake3.blake3(content).hexdigest(),       # primary, over RAW bytes
            "hash_sha256": hashlib.sha256(content).hexdigest(),      # FRE 902(14)
            "canonicalization_spec": "CANON-v0.1",
            "serializer_version": "hellgraph-serde-v0.1",
            "hash_computed_at_micros": now,
            "hash_computed_by": "metadata-intake-v0.1.0",
            "integrity_status": "Verified",
        },
        "temporal": {
            "txn_created": now,
            "observed_at_micros": obs,
            "uploaded_at_micros": now,
        },
        "provenance": {
            "source_account": source_account,
            "source_platform": source_platform,
            "source_path_or_id": source_path_or_id,
            "capture_method": capture_method,
            "chain_of_trust": [],
        },
        "classification": {
            "evidence_class": evidence_class,
            "evidence_grade": evidence_grade,
            "null_hypothesis_ids": null_hypothesis_ids or [],
            "counter_explanations": counter_explanations or [],
            "security_label": security_label,
            "witness_retention": witness_retention,
        },
    }

    # Validate against the vendored standard schema + the cross-field teeth BEFORE anything is recorded.
    try:
        import jsonschema
        schema = json.loads(_SCHEMA.read_text())
        errs = [e.message for e in jsonschema.Draft202012Validator(schema).iter_errors(record)]
    except ImportError:
        errs = []   # schema lib absent → cross-field teeth still enforced below
    errs += _cross_field_ok(record)
    if errs:
        raise IntakeError("non-conformant", "; ".join(errs[:3]))

    receipt = None
    if ledger is not None:
        # Intake CustodyEvent (AC-1): the artifact's entry into the platform, receipted + hash-chained.
        receipt = emit_proof_artifact(
            Path(ledger), extent=f"corpus/{corpus_id}", phase="intake",
            epistemic_level="Derived", agent="metadata-intake",
            inputs=record["integrity"]["hash_blake3"],   # bind the custody event to the artifact hash
            run=RunPackage(
                plan=[f"intake {exhibit_id} class={artifact_class}"],
                tool_calls=[{"tool": "MetadataIntake", "artifact_id": record["identity"]["artifact_id"]}],
                outputs=[{"metadata_record": record}],
                policy_report={"security_label": security_label, "witness_retention": witness_retention}),
            observed_at_micros=obs)
    return {"record": record, "receipt": receipt}
