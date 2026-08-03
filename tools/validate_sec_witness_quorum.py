#!/usr/bin/env python3
"""Validate SEC-2 witness-quorum blocks (structure + schema lockstep).

This validator enforces the STRUCTURE of a quorum block and keeps the published schema in
lockstep with the emitter's constants. The CRYPTOGRAPHIC teeth (a real 2-of-N quorum
verifies; under-quorum / tampered / unrostered signatures are refused; fail-closed promotion)
live in the functional test `tools/proof-artifact-spine/tests/sec2_test.py`.

Invariants enforced here (fail-closed):
- **FIPS scheme pinned.** scheme == "ecdsa-p256-quorum" (FROST/ed25519 is not accepted).
- **FIPS posture stated.** fips_posture is required and non-empty (mirrors how the spine made
  BLAKE3 advisory: the posture travels with the artifact).
- **Bound to a ProofArtifact.** committed.record_type == "ProofArtifact" and committed.entry_hash
  is a sha256 digest; signed_payload_hash is a sha256 digest.
- **Strict shape** (additionalProperties:false at every level).

Dependency-light (no jsonschema library), matching this repo's convention.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schemas/sec-witness-quorum.schema.json"
EXAMPLE = ROOT / "examples/sec-witness-quorum.example.json"
INVALID = [
    ROOT / "examples/sec-witness-quorum.wrong-scheme.invalid.json",
    ROOT / "examples/sec-witness-quorum.missing-fips-posture.invalid.json",
    ROOT / "examples/sec-witness-quorum.bad-entry-hash.invalid.json",
    ROOT / "examples/sec-witness-quorum.extra-field.invalid.json",
]

SHA256_RE = re.compile(r"^sha256:[a-f0-9]{64}$")
SCHEME = "ecdsa-p256-quorum"
ALG = "ECDSA_P256_SHA256"

TOP_KEYS = {"schema_version", "scheme", "threshold", "committed", "signed_payload_hash",
            "roster", "signatures", "fips_posture"}
THRESHOLD_KEYS = {"k", "n"}
COMMITTED_KEYS = {"record_type", "entry_hash"}
ROSTER_KEYS = {"witness_id", "alg", "public_key_spki_b64"}
SIG_KEYS = {"witness_id", "sig_b64"}


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


def no_extra(obj: dict[str, Any], allowed: set[str], ctx: str) -> None:
    extra = sorted(set(obj) - allowed)
    if extra:
        fail(f"unexpected fields in {ctx}: {extra}")


def require(obj: dict[str, Any], required: set[str], ctx: str) -> None:
    missing = sorted(required - set(obj))
    if missing:
        fail(f"{ctx} missing required fields: {missing}")


def validate_block(block: Any) -> None:
    if not isinstance(block, dict):
        fail("block must be an object")
    require(block, TOP_KEYS, "block")
    no_extra(block, TOP_KEYS, "block")

    if not re.fullmatch(r"^1\.[0-9]+$", need_str(block, "schema_version", "block")):
        fail("schema_version must match ^1\\.[0-9]+$")

    if block.get("scheme") != SCHEME:
        fail(f"scheme must be {SCHEME!r} (FROST/ed25519 is not FIPS-approved and is not accepted)")

    threshold = block.get("threshold")
    if not isinstance(threshold, dict):
        fail("threshold must be an object")
    require(threshold, THRESHOLD_KEYS, "threshold")
    no_extra(threshold, THRESHOLD_KEYS, "threshold")
    if not isinstance(threshold.get("k"), int) or threshold["k"] < 1:
        fail("threshold.k must be an integer >= 1")
    if not isinstance(threshold.get("n"), int) or threshold["n"] < 1:
        fail("threshold.n must be an integer >= 1")

    committed = block.get("committed")
    if not isinstance(committed, dict):
        fail("committed must be an object")
    require(committed, COMMITTED_KEYS, "committed")
    no_extra(committed, COMMITTED_KEYS, "committed")
    if committed.get("record_type") != "ProofArtifact":
        fail("committed.record_type must be 'ProofArtifact'")
    if not SHA256_RE.fullmatch(need_str(committed, "entry_hash", "committed")):
        fail("committed.entry_hash must be a sha256:<64hex> digest")

    if not SHA256_RE.fullmatch(need_str(block, "signed_payload_hash", "block")):
        fail("signed_payload_hash must be a sha256:<64hex> digest")

    roster = block.get("roster")
    if not isinstance(roster, list) or not roster:
        fail("roster must be a non-empty array")
    for r in roster:
        if not isinstance(r, dict):
            fail("roster entry must be an object")
        require(r, ROSTER_KEYS, "roster[]")
        no_extra(r, ROSTER_KEYS, "roster[]")
        need_str(r, "witness_id", "roster[]")
        if r.get("alg") != ALG:
            fail(f"roster[].alg must be {ALG!r}")
        need_str(r, "public_key_spki_b64", "roster[]")

    sigs = block.get("signatures")
    if not isinstance(sigs, list) or not sigs:
        fail("signatures must be a non-empty array")
    for s in sigs:
        if not isinstance(s, dict):
            fail("signature entry must be an object")
        require(s, SIG_KEYS, "signatures[]")
        no_extra(s, SIG_KEYS, "signatures[]")
        need_str(s, "witness_id", "signatures[]")
        need_str(s, "sig_b64", "signatures[]")

    need_str(block, "fips_posture", "block")  # posture must travel with the artifact


def validate_schema(schema: Any) -> None:
    """Assert the published schema stays in lockstep with this validator's invariants."""
    if not isinstance(schema, dict):
        fail("schema must be an object")
    if schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
        fail("schema must use JSON Schema draft 2020-12")
    if schema.get("additionalProperties") is not False:
        fail("schema root must be strict (additionalProperties:false)")
    if set(schema.get("required", [])) != TOP_KEYS:
        fail("schema root.required drifted from validator TOP_KEYS")
    props = schema.get("properties", {})
    if props.get("scheme", {}).get("const") != SCHEME:
        fail("schema must pin scheme const 'ecdsa-p256-quorum' (FIPS posture)")
    committed = props.get("committed", {})
    if committed.get("properties", {}).get("record_type", {}).get("const") != "ProofArtifact":
        fail("schema must pin committed.record_type const 'ProofArtifact'")
    roster_items = props.get("roster", {}).get("items", {})
    if roster_items.get("properties", {}).get("alg", {}).get("const") != ALG:
        fail("schema must pin roster[].alg const 'ECDSA_P256_SHA256'")


def main() -> int:
    try:
        validate_schema(load(SCHEMA))     # schema exercised, not just parsed
        validate_block(load(EXAMPLE))     # canonical example must pass
        for path in INVALID:
            try:
                validate_block(load(path))
            except ValidationError:
                continue
            fail(f"expected {path.name} to be rejected, but it passed")
    except ValidationError as exc:
        print(f"ERR: {exc}", file=sys.stderr)
        return 2
    print(f"OK: SEC-2 witness-quorum validation passed "
          f"(schema in lockstep, 1 example, {len(INVALID)} invalid rejected)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
