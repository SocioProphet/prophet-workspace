"""CustodyEvent model — the full 14-type chain-of-custody enumeration (MS-P4, Metadata Standards §6).

Every interaction with an artifact appends a CustodyEvent to the append-only custody log. Events share
the SAME FIPS-approved (SHA-256) hash-chain as ProofArtifacts (one spine, multiple record types), so a
mixed ledger verifies with the existing verify_ledger. Each event type declares its mandatory fields
(§6.2); emission is fail-closed and rejects an event missing any mandatory field.

FIPS: the chain hash is SHA-256 (see proof_artifact.CHAIN_ALGO). No BLAKE3 in the chain.
"""
from __future__ import annotations

import time
from pathlib import Path

from proof_artifact import (  # reuse the FIPS-approved chain + ledger primitives (one spine)
    GENESIS_PREV, ProofArtifactError, _last_entry, canonical, chain_hash,
)

RECORD_TYPE = "CustodyEvent"

ACTOR_TYPES = {"HumanUser", "IntakeProcess", "AnalysisAgent", "AIAgent", "ExportProcess", "VerificationProcess"}
CUSTODY_STATUS = {"Intact", "Gap", "IntegrityViolation", "PendingVerification"}
ZONES = {"Discovery", "Landing", "Examination", "Integration", "Governed", "Diamond", "Streaming"}

# §6.2 — the 14 event types and the fields each one MANDATES (beyond the always-required base fields
# artifact_id, actor_id, actor_type, timestamp_micros).
EVENT_TYPES: dict[str, list[str]] = {
    "Intake":            ["hash_at_event", "zone_to"],
    "HashVerification":  ["hash_at_event", "custody_status"],
    "ZonePromotion":     ["zone_from", "zone_to", "tool_name"],
    "ZoneDemotion":      ["zone_from", "zone_to", "note"],
    "Examination":       ["tool_name", "hash_at_event"],
    "EnrichmentWrite":   ["tool_name"],
    "HypothesisLink":    ["hypothesis_ids"],
    "Read":              [],
    "ExportBundled":     ["hash_at_event", "trpc_commit_receipt"],
    "Disclosed":         ["recipient_id", "trpc_commit_receipt"],
    "IntegrityViolation":["hash_at_event", "note", "custody_status"],
    "PolicyException":   ["zone_from", "zone_to", "note"],
    "ManualOverride":    ["note"],
    "Retirement":        ["note"],
}


class CustodyEventError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


def emit_custody_event(
    ledger: Path,
    *,
    event_type: str,
    artifact_id: str,
    actor_id: str,
    actor_type: str,
    timestamp_micros: int | None = None,
    **fields,
) -> dict:
    """Append a hash-chained CustodyEvent. Validates the type, actor_type, and the type's mandatory
    fields BEFORE writing. Fail-closed: a ledger write error raises (no event = no custody claim)."""
    if event_type not in EVENT_TYPES:
        raise CustodyEventError("unknown-event-type", f"{event_type!r} not in the 14 CustodyEvent types")
    if actor_type not in ACTOR_TYPES:
        raise CustodyEventError("bad-actor-type", f"{actor_type!r} not a valid actor_type")
    missing = [f for f in EVENT_TYPES[event_type] if fields.get(f) in (None, "", [], {})]
    if missing:
        raise CustodyEventError("missing-mandatory", f"{event_type} requires {missing}")
    # typed-field sanity (only when supplied)
    if "custody_status" in fields and fields["custody_status"] not in CUSTODY_STATUS:
        raise CustodyEventError("bad-custody-status", str(fields["custody_status"]))
    for zk in ("zone_from", "zone_to"):
        if fields.get(zk) is not None and fields[zk] not in ZONES:
            raise CustodyEventError("bad-zone", f"{zk}={fields[zk]!r}")
    if event_type == "IntegrityViolation" and fields.get("custody_status") != "IntegrityViolation":
        raise CustodyEventError("status-mismatch", "IntegrityViolation event must set custody_status=IntegrityViolation")

    ledger = Path(ledger)
    prev = _last_entry(ledger)
    prev_hash = prev["entryHash"] if prev else GENESIS_PREV
    seq = (prev["ledgerSeq"] + 1) if prev else 0
    ts = timestamp_micros if timestamp_micros is not None else int(time.time() * 1_000_000)

    body = {
        "recordType": RECORD_TYPE,
        "ledgerSeq": seq,
        "ledgerPrevHash": prev_hash,
        "eventType": event_type,
        "artifactId": artifact_id,
        "actorId": actor_id,
        "actorType": actor_type,
        "timestampMicros": ts,
        "fields": {k: v for k, v in fields.items() if v not in (None,)},
    }
    body["entryHash"] = chain_hash(prev_hash + canonical(body))   # chain = SHA-256 (FIPS)
    try:
        with open(ledger, "a", encoding="utf-8") as f:
            f.write(canonical(body) + "\n")
    except OSError as e:
        raise ProofArtifactError(f"ledger write failed: {e}") from e
    return body
