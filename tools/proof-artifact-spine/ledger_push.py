"""Ledger.Push — the ONE physical append onto the estate receipt spine (WO-B of ADR-0001).

ADR-0001 names a `Ledger.Push` triRPC verb as the productionisation of the receipt spine: every
record type — ProofArtifact (knowledge publishes), InferenceReceipt (embeddings/completions,
prophet-platform #1233/#1237), CustodyEvent (chain-of-custody, MS-P4) — appends to ONE append-only,
tamper-evident ledger through the SAME FIPS-approved (SHA-256) hash chain.

Before this module each emitter hand-rolled the identical read-prev → seq → build-body → chain-hash →
append sequence (proof_artifact.emit_proof_artifact, custody_event.emit_custody_event). That is three
copies of one invariant — and an invariant copied three times is an invariant that will drift. This
module is the single owner of that sequence; the emitters become thin field-shapers that call it. One
spine, one append, many record types.

Design notes:
  - Key order is irrelevant to the chain: `canonical()` sorts keys, so routing an EXISTING emitter's
    body through `ledger_push` produces byte-identical entryHashes (the conformance suites are the
    proof — they stay green across the refactor).
  - The four spine-owned keys (recordType, ledgerSeq, ledgerPrevHash, entryHash) are reserved; a caller
    that tries to set one in `fields` is rejected loudly (it would corrupt the chain semantics).
  - Fail-closed: a ledger write error raises (no entry ⇒ no receipt ⇒ no publish, AC-1).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

# The spine primitives live in proof_artifact (the original arm); import them here so this module owns
# only the append verb. proof_artifact does a DEFERRED import of ledger_push inside its emitter, so
# there is no import cycle.
from proof_artifact import (
    GENESIS_PREV,
    ProofArtifactError,
    _last_entry,
    canonical,
    chain_hash,
    dual_hash,
)

# Keys the spine owns; a record's own fields may never collide with these.
_RESERVED = ("recordType", "ledgerSeq", "ledgerPrevHash", "entryHash")


class LedgerPushError(Exception):
    """Ledger.Push could not append (write failure or an illegal request). Callers fail closed."""


def ledger_push(
    ledger: Path | str,
    *,
    record_type: str,
    fields: dict,
    error_cls: type[Exception] = ProofArtifactError,
) -> dict:
    """Append one hash-chained entry of `record_type` carrying `fields`, and return it.

    This is the sole physical writer of the spine: it reads the prior entry, assigns the next
    monotonic `ledgerSeq`, links `ledgerPrevHash`, builds the body as {recordType, ledgerSeq,
    ledgerPrevHash, **fields}, stamps the FIPS SHA-256 `entryHash` over prevHash+canonical(body), and
    appends one canonical-JSON line. `error_cls` lets an arm keep its own fail-closed exception type
    (e.g. ProofArtifactError) so existing callers' contracts are unchanged."""
    if not record_type:
        raise LedgerPushError("record_type is required")
    collisions = [k for k in _RESERVED if k in fields]
    if collisions:
        raise LedgerPushError(f"fields may not set spine-owned keys {collisions}")

    ledger = Path(ledger)
    prev = _last_entry(ledger)
    prev_hash = prev["entryHash"] if prev else GENESIS_PREV
    seq = (prev["ledgerSeq"] + 1) if prev else 0

    body = {"recordType": record_type, "ledgerSeq": seq, "ledgerPrevHash": prev_hash, **fields}
    body["entryHash"] = chain_hash(prev_hash + canonical(body))   # chain = SHA-256 (FIPS)

    try:
        with open(ledger, "a", encoding="utf-8") as f:
            f.write(canonical(body) + "\n")
    except OSError as e:
        raise error_cls(f"ledger write failed: {e}") from e
    return body


# ── the triRPC verb surface (thin request/response over ledger_push) ──────────────────────────
@dataclass(frozen=True)
class LedgerPushRequest:
    """A `Ledger.Push` call: which record type, and its already-shaped, spine-agnostic fields."""
    record_type: str
    fields: dict = field(default_factory=dict)


@dataclass(frozen=True)
class LedgerPushResponse:
    entry: dict

    @property
    def ledger_seq(self) -> int:
        return self.entry["ledgerSeq"]

    @property
    def entry_hash(self) -> str:
        return self.entry["entryHash"]


def handle_ledger_push(req: LedgerPushRequest, ledger: Path | str) -> LedgerPushResponse:
    """Reference handler for the `Ledger.Push` verb — validates and appends. A network service (triRPC)
    is a thin transport over exactly this."""
    entry = ledger_push(ledger, record_type=req.record_type, fields=req.fields, error_cls=LedgerPushError)
    return LedgerPushResponse(entry=entry)


# ── InferenceReceipt arm — the sibling record type the spine was always meant to share ─────────
INFERENCE_RECORD_TYPE = "InferenceReceipt"


def emit_inference_receipt(
    ledger: Path | str,
    *,
    kind: str,
    actor: str,
    inputs: str,
    outputs: str,
    epistemic_status: str = "Derived",
) -> dict:
    """Append an InferenceReceipt (embedding/completion/etc.) onto the SAME physical ledger as
    ProofArtifacts and CustodyEvents, via Ledger.Push. Dual-hashed (SHA-256 authoritative + BLAKE3
    advisory) exactly like the ProofArtifact arm, so one `verify_ledger` walk covers the mixed chain."""
    return ledger_push(
        ledger,
        record_type=INFERENCE_RECORD_TYPE,
        fields={
            "kind": kind,
            "actor": actor,
            "epistemicStatus": epistemic_status,
            "inputHash": dual_hash(inputs),
            "outputHash": dual_hash(outputs),
        },
    )


__all__ = [
    "LedgerPushError",
    "ledger_push",
    "LedgerPushRequest",
    "LedgerPushResponse",
    "handle_ledger_push",
    "emit_inference_receipt",
    "INFERENCE_RECORD_TYPE",
]
