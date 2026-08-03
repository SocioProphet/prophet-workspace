"""ProofArtifact emitter — the KNOWLEDGE-publish arm of the estate receipt spine (WO-B of ADR-0001).

The receipt-gateway already receipts *inference* publishes (InferenceReceipt: embeddings/completions,
prophet-platform #1233/#1237). WO-B extends the SAME hash-chained ledger discipline to *knowledge*
publishes: every workspace f_! (write a fact, close a case, promote a chunk, ship an image) emits a
ProofArtifact carrying the run package (plan, tool_calls, outputs, policy_report) plus input/output
hashes, chained to the previous entry via ledgerPrevHash. One spine, two record types.

Mechanics deliberately mirror inference_receipt_emitter (canonical JSON + sha256 + prevHash + seq) so
both record types share one append-only, tamper-evident ledger. Productionising = routing these through
the shared ledger service behind the `Ledger.Push` triRPC verb (ADR-0001); this module is the contract
+ a runnable reference.
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from pathlib import Path

import blake3  # noqa: E402 — BLAKE3-256 is the PRIMARY integrity fingerprint (Metadata Standards v0.1)

RECORD_TYPE = "ProofArtifact"
GENESIS_PREV = "blake3:" + "0" * 64   # first entry chains to genesis (chain hash = BLAKE3, primary)


def blake3_hex(s: str) -> str:
    """Primary integrity fingerprint (Metadata Standards §3.2: BLAKE3-256, before any conversion)."""
    return "blake3:" + blake3.blake3(s.encode("utf-8")).hexdigest()


def sha256(s: str) -> str:
    """Secondary fingerprint — FRE 902(14) compatibility + external verifier interop."""
    return "sha256:" + hashlib.sha256(s.encode("utf-8")).hexdigest()


def dual_hash(s: str) -> dict:
    """The standard's dual-hash: BLAKE3 primary + SHA-256 for legal/interop. Both over the same bytes."""
    return {"blake3": blake3_hex(s), "sha256": sha256(s)}


def canonical(obj: dict) -> str:
    """Deterministic JSON for hashing/chaining (sorted keys, no whitespace, stable separators)."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


class ProofArtifactError(Exception):
    pass


@dataclass
class RunPackage:
    """The Quilt-style portable run package a knowledge publish produces."""
    plan: list[str] = field(default_factory=list)
    tool_calls: list[dict] = field(default_factory=list)
    outputs: list[dict] = field(default_factory=list)
    policy_report: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"plan": self.plan, "tool_calls": self.tool_calls,
                "outputs": self.outputs, "policy_report": self.policy_report}


def _last_entry(ledger: Path) -> dict | None:
    if not ledger.exists():
        return None
    last = None
    with open(ledger, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                last = json.loads(line)
    return last


def emit_proof_artifact(
    ledger: Path,
    *,
    extent: str,
    phase: str,
    epistemic_level: str,
    agent: str,
    inputs: str,
    run: RunPackage,
    inclusion_record: dict | None = None,
    observed_at_micros: int | None = None,
) -> dict:
    """Append a hash-chained ProofArtifact for a knowledge publish. Returns the receipt.

    Raises ProofArtifactError if the ledger can't be written — the caller (publish/f_!) MUST treat that
    as a failed publish (AC-1: no receipt ⇒ no publish)."""
    ledger = Path(ledger)
    prev = _last_entry(ledger)
    prev_hash = prev["entryHash"] if prev else GENESIS_PREV
    seq = (prev["ledgerSeq"] + 1) if prev else 0

    now_micros = int(time.time() * 1_000_000)
    run_dict = run.to_dict()
    body = {
        "recordType": RECORD_TYPE,
        "ledgerSeq": seq,
        "ledgerPrevHash": prev_hash,
        # Three-time model (Metadata Standards §3.3): observed = when the action was produced;
        # txn_created = ledger write; uploaded = commit to the durable ledger. Distinct, never conflated.
        "temporal": {
            "observed_at_micros": observed_at_micros if observed_at_micros is not None else now_micros,
            "txn_created": now_micros,
            "uploaded_at_micros": now_micros,
        },
        "extent": extent,
        "phase": phase,
        "epistemicLevel": epistemic_level,   # e.g. Derived (external principals capped here — STAR-1)
        "agent": agent,
        # Dual-hash (BLAKE3 primary + SHA-256) over the inputs and the canonical run package.
        "inputHash": dual_hash(inputs),
        "outputHash": dual_hash(canonical(run_dict)),
        "runPackage": run_dict,
        "inclusionRecord": inclusion_record or {},
    }
    body["entryHash"] = blake3_hex(prev_hash + canonical(body))   # chain = BLAKE3 primary

    try:
        with open(ledger, "a", encoding="utf-8") as f:
            f.write(canonical(body) + "\n")
    except OSError as e:
        raise ProofArtifactError(f"ledger write failed: {e}") from e
    return body


def verify_ledger(ledger: Path) -> tuple[bool, str]:
    """Verify the whole chain: seq monotonic, prevHash links, and each entryHash recomputes.
    Returns (ok, message). Tamper anywhere breaks it."""
    ledger = Path(ledger)
    if not ledger.exists():
        return True, "empty ledger"
    prev_hash = GENESIS_PREV
    expected_seq = 0
    with open(ledger, encoding="utf-8") as f:
        for i, line in enumerate(f):
            line = line.strip()
            if not line:
                continue
            entry = json.loads(line)
            if entry.get("ledgerSeq") != expected_seq:
                return False, f"seq gap at line {i}: got {entry.get('ledgerSeq')}, expected {expected_seq}"
            if entry.get("ledgerPrevHash") != prev_hash:
                return False, f"broken chain at seq {entry.get('ledgerSeq')}: prevHash mismatch"
            claimed = entry.get("entryHash")
            body = {k: v for k, v in entry.items() if k != "entryHash"}
            recomputed = blake3_hex(prev_hash + canonical(body))   # chain = BLAKE3 primary
            if recomputed != claimed:
                return False, f"tamper at seq {entry.get('ledgerSeq')}: entryHash mismatch"
            prev_hash = claimed
            expected_seq += 1
    return True, f"chain valid ({expected_seq} entries)"
