#!/usr/bin/env python3
"""Validate SEC-1 Event-IR records (Agentic SecOps Immune System, observe layer).

Event-IR is the normalized typed sensor event that feeds ProofArtifact claims
(tools/proof-artifact-spine). Invariants enforced here (fail-closed):

- **Versioned.** schema_version must match ^1\\.[0-9]+$.
- **Explicit provenance.** provenance.{collector,toolchain,inputs,privacy} are all
  required — no anonymous events enter the immune system.
- **Privacy-labelled.** provenance.privacy.tier must be one of local_only |
  proof_only | share_aggregate. An unknown tier is rejected (a leak would otherwise
  travel further than intended).
- **Immune-system labels.** subject.labels.surface must be H1..H7; subject.labels.topic
  must be LDA_01..LDA_23 (the estate's 23-topic taxonomy).
- **Strict shape.** additionalProperties:false at every level — unknown fields fail
  closed here, not silently downstream.
- **Deterministic canonical encoding.** The record encodes byte-identically under the
  SAME encoder as the receipt spine (proof_artifact.canonical), independent of key
  order, so an Event-IR can be hash-committed into a ProofArtifact. This validator
  imports the spine's canonical() rather than re-implementing it, so the two cannot drift.

Dependency-light (no jsonschema library), matching this repo's convention
(cf. tools/validate_sp_file_naming.py). Also asserts the published schema stays in
lockstep with these invariants so the two cannot silently diverge.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schemas/sec-event-ir.schema.json"
EXAMPLE = ROOT / "examples/sec-event-ir.example.json"
INVALID = [
    ROOT / "examples/sec-event-ir.bad-privacy-tier.invalid.json",
    ROOT / "examples/sec-event-ir.missing-provenance.invalid.json",
    ROOT / "examples/sec-event-ir.bad-surface.invalid.json",
    ROOT / "examples/sec-event-ir.bad-topic.invalid.json",
    ROOT / "examples/sec-event-ir.extra-field.invalid.json",
]

# Reuse the receipt spine's canonical encoder + hash — single source of truth, no drift.
sys.path.insert(0, str(ROOT / "tools/proof-artifact-spine"))
from proof_artifact import canonical, sha256  # noqa: E402

SCHEMA_VERSION_RE = re.compile(r"^1\.[0-9]+$")
TOPIC_RE = re.compile(r"^LDA_(0[1-9]|1[0-9]|2[0-3])$")
SURFACES = {"H1", "H2", "H3", "H4", "H5", "H6", "H7"}
PRIVACY_TIERS = {"local_only", "proof_only", "share_aggregate"}
KINDS = {
    "NET_TLS_HANDSHAKE", "NET_CONNECT", "DNS_QUERY", "FILE_WRITE", "FILE_READ",
    "PROCESS_EXEC", "POLICY_CHANGE", "PRIVILEGE_CHANGE", "BOOT_ATTEST", "KEY_USE",
    "AUTH_ATTEMPT", "MOUNT_CHANGE", "CONFIG_READ", "EDITOR_LSP_MSG", "SOURCE_EDIT",
}

TOP_KEYS = {"schema_version", "event_id", "time", "kind", "subject", "facts", "provenance"}
SUBJECT_KEYS = {"scope", "labels"}
LABEL_KEYS = {"surface", "topic"}
PROV_KEYS = {"collector", "toolchain", "inputs", "privacy"}
PRIVACY_KEYS = {"tier"}


class ValidationError(Exception):
    pass


def fail(message: str) -> None:
    raise ValidationError(message)


def load(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValidationError(f"missing file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValidationError(f"invalid JSON in {path}: {exc}") from exc


def need_str(obj: dict[str, Any], key: str, ctx: str) -> str:
    value = obj.get(key)
    if not isinstance(value, str) or not value:
        fail(f"{ctx}.{key}: expected non-empty string")
    return value  # type: ignore[return-value]


def need_obj(obj: dict[str, Any], key: str, ctx: str) -> dict[str, Any]:
    value = obj.get(key)
    if not isinstance(value, dict):
        fail(f"{ctx}.{key}: expected object")
    return value  # type: ignore[return-value]


def no_extra(obj: dict[str, Any], allowed: set[str], ctx: str) -> None:
    extra = sorted(set(obj) - allowed)
    if extra:
        fail(f"unexpected fields in {ctx}: {extra}")


def require(obj: dict[str, Any], required: set[str], ctx: str) -> None:
    missing = sorted(required - set(obj))
    if missing:
        fail(f"{ctx} missing required fields: {missing}")


def validate_event(record: Any) -> None:
    """Enforce the SEC-1 invariants on one Event-IR record. Raises ValidationError."""
    if not isinstance(record, dict):
        fail("record must be an object")
    require(record, TOP_KEYS, "record")
    no_extra(record, TOP_KEYS, "record")

    version = need_str(record, "schema_version", "record")
    if not SCHEMA_VERSION_RE.fullmatch(version):
        fail("schema_version must match ^1\\.[0-9]+$")

    need_str(record, "event_id", "record")

    ts = need_str(record, "time", "record")
    try:
        datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        fail("time must be an RFC3339/ISO-8601 date-time")

    kind = need_str(record, "kind", "record")
    if kind not in KINDS:
        fail(f"kind {kind!r} is not a known Event-IR kind")

    if not isinstance(record.get("facts"), dict):
        fail("facts must be an object")

    # subject + immune-system labels
    subject = need_obj(record, "subject", "record")
    require(subject, SUBJECT_KEYS, "subject")
    no_extra(subject, SUBJECT_KEYS, "subject")
    need_str(subject, "scope", "subject")
    labels = need_obj(subject, "labels", "subject")
    require(labels, LABEL_KEYS, "subject.labels")
    no_extra(labels, LABEL_KEYS, "subject.labels")
    surface = need_str(labels, "surface", "subject.labels")
    if surface not in SURFACES:
        fail(f"subject.labels.surface {surface!r} must be one of H1..H7")
    topic = need_str(labels, "topic", "subject.labels")
    if not TOPIC_RE.fullmatch(topic):
        fail(f"subject.labels.topic {topic!r} must match LDA_01..LDA_23")

    # explicit provenance
    prov = need_obj(record, "provenance", "record")
    require(prov, PROV_KEYS, "provenance")
    no_extra(prov, PROV_KEYS, "provenance")
    need_str(prov, "collector", "provenance")
    need_str(prov, "toolchain", "provenance")
    inputs = prov.get("inputs")
    if not isinstance(inputs, list) or not all(isinstance(i, str) and i for i in inputs):
        fail("provenance.inputs must be an array of non-empty strings (may be empty)")
    if len(inputs) != len(set(inputs)):
        fail("provenance.inputs must be unique")

    # privacy label
    privacy = need_obj(prov, "privacy", "provenance")
    require(privacy, PRIVACY_KEYS, "provenance.privacy")
    no_extra(privacy, PRIVACY_KEYS, "provenance.privacy")
    tier = need_str(privacy, "tier", "provenance.privacy")
    if tier not in PRIVACY_TIERS:
        fail(f"provenance.privacy.tier {tier!r} must be one of {sorted(PRIVACY_TIERS)}")


def validate_schema(schema: Any) -> None:
    """Exercise the published schema and assert it stays in lockstep with this validator's
    invariants, so the two cannot silently drift (dependency-light: no jsonschema library)."""
    if not isinstance(schema, dict):
        fail("schema must be an object")
    if schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
        fail("schema must use JSON Schema draft 2020-12")
    if schema.get("additionalProperties") is not False:
        fail("schema root must be strict (additionalProperties:false)")
    if set(schema.get("required", [])) != TOP_KEYS:
        fail("schema root.required drifted from validator TOP_KEYS")
    props = schema.get("properties", {})

    if set(props.get("kind", {}).get("enum", [])) != KINDS:
        fail("schema kind.enum drifted from validator KINDS")

    subject = props.get("subject", {})
    if subject.get("additionalProperties") is not False:
        fail("schema subject must be strict")
    labels = subject.get("properties", {}).get("labels", {})
    if labels.get("additionalProperties") is not False:
        fail("schema subject.labels must be strict")
    label_props = labels.get("properties", {})
    if set(label_props.get("surface", {}).get("enum", [])) != SURFACES:
        fail("schema surface.enum drifted from validator SURFACES (H1..H7)")
    if label_props.get("topic", {}).get("pattern") != "^LDA_(0[1-9]|1[0-9]|2[0-3])$":
        fail("schema topic.pattern drifted from validator (LDA_01..LDA_23)")

    prov = props.get("provenance", {})
    if prov.get("additionalProperties") is not False:
        fail("schema provenance must be strict")
    if set(prov.get("required", [])) != PROV_KEYS:
        fail("schema provenance.required drifted from validator PROV_KEYS")
    privacy = prov.get("properties", {}).get("privacy", {})
    if set(privacy.get("properties", {}).get("tier", {}).get("enum", [])) != PRIVACY_TIERS:
        fail("schema privacy.tier.enum drifted from validator PRIVACY_TIERS")


def check_canonical_determinism(record: dict[str, Any]) -> None:
    """The Event-IR must encode deterministically under the SPINE's canonical() encoder,
    independent of key insertion order, so it can be hash-committed into a ProofArtifact.
    Teeth: encode twice (stable), encode a key-shuffled copy (order-independent), and
    confirm the encoder is exactly the spine's (sorted keys, no whitespace)."""
    enc1 = canonical(record)
    enc2 = canonical(record)
    if enc1 != enc2:
        fail("canonical encoding is not stable across calls")

    # rebuild with reversed key order at every level -> canonical form must be identical
    def reorder(obj: Any) -> Any:
        if isinstance(obj, dict):
            return {k: reorder(obj[k]) for k in reversed(list(obj.keys()))}
        if isinstance(obj, list):
            return [reorder(x) for x in obj]
        return obj

    if canonical(reorder(record)) != enc1:
        fail("canonical encoding is not key-order-independent")

    # must be the spine encoder's contract: sorted keys, compact separators
    if enc1 != json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False):
        fail("canonical encoding does not match the spine encoder contract")

    # content-address is well-formed (sha256:<64hex>)
    cid = sha256(enc1)
    if not re.fullmatch(r"sha256:[a-f0-9]{64}", cid):
        fail("content-address of canonical encoding is malformed")


def main() -> int:
    try:
        validate_schema(load(SCHEMA))          # schema exercised, not just parsed
        example = load(EXAMPLE)
        validate_event(example)                # canonical example must pass
        check_canonical_determinism(example)   # deterministic encoding (spine encoder)
        for path in INVALID:
            try:
                validate_event(load(path))
            except ValidationError:
                continue
            fail(f"expected {path.name} to be rejected, but it passed")
    except ValidationError as exc:
        print(f"ERR: {exc}", file=sys.stderr)
        return 2
    print(f"OK: SEC-1 Event-IR validation passed "
          f"(schema in lockstep, 1 example, {len(INVALID)} invalid rejected, canonical encoding stable)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
