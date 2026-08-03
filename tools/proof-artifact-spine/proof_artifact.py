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

RECORD_TYPE = "ProofArtifact"
GENESIS_PREV = "sha256:" + "0" * 64   # first entry chains to genesis


def sha256(s: str) -> str:
    return "sha256:" + hashlib.sha256(s.encode("utf-8")).hexdigest()


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
) -> dict:
    """Append a hash-chained ProofArtifact for a knowledge publish. Returns the receipt.

    Raises ProofArtifactError if the ledger can't be written — the caller (publish/f_!) MUST treat that
    as a failed publish (AC-1: no receipt ⇒ no publish)."""
    ledger = Path(ledger)
    prev = _last_entry(ledger)
    prev_hash = prev["entryHash"] if prev else GENESIS_PREV
    seq = (prev["ledgerSeq"] + 1) if prev else 0

    run_dict = run.to_dict()
    body = {
        "recordType": RECORD_TYPE,
        "ledgerSeq": seq,
        "ledgerPrevHash": prev_hash,
        "emittedAt": round(time.time(), 3),
        "extent": extent,
        "phase": phase,
        "epistemicLevel": epistemic_level,   # e.g. Derived (external principals capped here — STAR-1)
        "agent": agent,
        "inputHash": sha256(inputs),
        "outputHash": sha256(canonical(run_dict)),
        "runPackage": run_dict,
        "inclusionRecord": inclusion_record or {},
    }
    body["entryHash"] = sha256(prev_hash + canonical(body))

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
            recomputed = sha256(prev_hash + canonical(body))
            if recomputed != claimed:
                return False, f"tamper at seq {entry.get('ledgerSeq')}: entryHash mismatch"
            prev_hash = claimed
            expected_seq += 1
    return True, f"chain valid ({expected_seq} entries)"
