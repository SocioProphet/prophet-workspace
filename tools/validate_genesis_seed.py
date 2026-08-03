#!/usr/bin/env python3
"""Validate GenesisSeed records (WO-J, Open Agent Continuum / ADR-0001).

A Genesis seed is the reusable FORMATION artifact: a signed, typed operating charter that Inception
binds into a live twin. Genesis is compile-time and reusable; Inception is runtime and contextual. A
seed is NOT a free-form prompt — it declares role archetype, ontology slice, allowed organs, and the
retrieval/memory/policy/provider/federation/approval profiles a twin may operate within.

Consume-not-fork bindings (the seed does not re-implement anything the continuum already built):
  - organs_allowed / provider_profile INSTANTIATE into a WorkspaceMountTable (schemas/workspace-mount-
    table.schema.json, the f* capability surface);
  - policy_profile modules are served by Sentinel/OPA — the seed only references them;
  - provenance memory is the ProofArtifact spine (tools/proof-artifact-spine, the f_! receipt arm);
  - the seed's epistemic ceiling is computed by tools/workspace-controller (meet over mounted sections,
    external clamp to Derived).

Invariants (fail-closed), teeth both ways:
  - **Shape.** additionalProperties:false everywhere; all required fields present; enumerated modes.
  - **Append-only provenance (spec 7.4 / AC-1).** memory_profile.provenance MUST be "append_only" — a
    seed that lets a twin rewrite or erase provenance is a bug, not a feature.
  - **Fail-closed actuation (spec non-negotiable #1 / ADR actuation gate).** If provider_profile grants
    any mutating/host provider (provider:kubernetes | provider:host | a *host_update* provider), then
    approval_profile.host_mutation MUST be "required". No unguarded world mutation.
  - **Bounded federation (ADR federation gate).** federation_profile is a closed enum — a seed cannot
    self-declare unbounded cross-domain federation.

Mirrors the schema's additionalProperties:false in the record checks (extra keys fail closed here, not
only against the JSON Schema), and exercises the schema so the two cannot silently drift — dependency-
light, matching this repo's convention (no jsonschema library). Excludes itself from what it validates.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schemas/genesis-seed.schema.json"
EXAMPLE = ROOT / "examples/genesis-seed.example.json"
INVALID = [
    ROOT / "examples/genesis-seed.provenance-writable.invalid.json",
    ROOT / "examples/genesis-seed.unguarded-host-mutation.invalid.json",
]

SPEC_KEYS = {
    "seed_id", "archetype", "ontology_slice", "goal_schema", "organs_allowed",
    "retrieval_profile", "memory_profile", "policy_profile", "provider_profile",
    "federation_profile", "approval_profile",
}
RETRIEVAL_KEYS = {"graph", "hybrid", "multimodal", "self_reflective", "recursive"}
MEMORY_KEYS = {"episodic", "semantic", "procedural", "provenance"}
MEMORY_MODES = {"none", "read", "read_write", "read_write_scoped", "append_only"}
FEDERATION_MODES = {"none", "same_domain_only", "cross_domain_reviewed"}
APPROVAL_STATES = {"required", "optional", "not_required"}

# Providers whose use implies host/world mutation → force a human gate.
_MUTATING_PROVIDERS = {"provider:kubernetes", "provider:host"}


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


def need_str(obj: dict[str, Any], key: str) -> str:
    value = obj.get(key)
    if not isinstance(value, str) or not value:
        fail(f"{key}: expected non-empty string")
    return value  # type: ignore[return-value]


def need_str_list(obj: dict[str, Any], key: str, *, min_items: int) -> list[str]:
    value = obj.get(key)
    if not isinstance(value, list) or len(value) < min_items:
        fail(f"{key}: expected array with at least {min_items} item(s)")
    if any(not isinstance(v, str) or not v for v in value):
        fail(f"{key}: every item must be a non-empty string")
    if len(set(value)) != len(value):
        fail(f"{key}: items must be unique (the profile is a set)")
    return value  # type: ignore[return-value]


def no_extra(obj: dict[str, Any], allowed: set[str], ctx: str) -> None:
    extra = sorted(set(obj) - allowed)
    if extra:
        fail(f"unexpected fields in {ctx}: {extra}")


def _mutates_host(provider_profile: list[str]) -> bool:
    for p in provider_profile:
        if p in _MUTATING_PROVIDERS or "host_update" in p:
            return True
    return False


def validate_genesis_seed(record: Any) -> None:
    """Enforce the WO-J invariants on one GenesisSeed. Raises ValidationError."""
    if not isinstance(record, dict):
        fail("record must be an object")
    no_extra(record, SPEC_KEYS, "record")

    need_str(record, "seed_id")
    need_str(record, "archetype")
    need_str(record, "goal_schema")
    need_str_list(record, "ontology_slice", min_items=1)
    need_str_list(record, "organs_allowed", min_items=1)
    need_str_list(record, "policy_profile", min_items=1)
    provider_profile = need_str_list(record, "provider_profile", min_items=0)

    # retrieval_profile — every flag present and boolean
    retrieval = record.get("retrieval_profile")
    if not isinstance(retrieval, dict):
        fail("retrieval_profile: expected object")
    no_extra(retrieval, RETRIEVAL_KEYS, "retrieval_profile")
    for k in RETRIEVAL_KEYS:
        if not isinstance(retrieval.get(k), bool):
            fail(f"retrieval_profile.{k}: expected boolean")

    # memory_profile — every stratum present, from the mode vocabulary; provenance append-only.
    memory = record.get("memory_profile")
    if not isinstance(memory, dict):
        fail("memory_profile: expected object")
    no_extra(memory, MEMORY_KEYS, "memory_profile")
    for k in MEMORY_KEYS:
        if memory.get(k) not in MEMORY_MODES:
            fail(f"memory_profile.{k} must be one of {sorted(MEMORY_MODES)}")
    # APPEND-ONLY PROVENANCE LAW (spec 7.4 / AC-1): provenance is never rewritten.
    if memory.get("provenance") != "append_only":
        fail("memory_profile.provenance must be 'append_only' — provenance memory is never "
             "rewritten (a later correction references, never erases, the earlier state)")

    # federation_profile — closed enum (bounded federation).
    if record.get("federation_profile") not in FEDERATION_MODES:
        fail(f"federation_profile must be one of {sorted(FEDERATION_MODES)}")

    # approval_profile — object keyed by action kind, values from the approval-state vocabulary.
    approval = record.get("approval_profile")
    if not isinstance(approval, dict):
        fail("approval_profile: expected object")
    for action, state in approval.items():
        if state not in APPROVAL_STATES:
            fail(f"approval_profile.{action} must be one of {sorted(APPROVAL_STATES)}")

    # FAIL-CLOSED ACTUATION (spec non-negotiable #1 / ADR actuation gate): a mutating/host provider
    # forces a required human gate on host_mutation.
    if _mutates_host(provider_profile) and approval.get("host_mutation") != "required":
        fail("fail-closed actuation: provider_profile grants a mutating/host provider "
             f"({sorted(_MUTATING_PROVIDERS)} or *host_update*), so approval_profile.host_mutation "
             "must be 'required'")


def validate_schema(schema: Any) -> None:
    """Exercise the published schema and assert it stays in lockstep with this validator's invariants,
    so the two cannot silently drift (dependency-light, per repo convention)."""
    if not isinstance(schema, dict):
        fail("schema must be an object")
    if schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
        fail("schema must use JSON Schema draft 2020-12")
    if schema.get("additionalProperties") is not False:
        fail("schema root must be strict (additionalProperties:false)")
    if set(schema.get("required", [])) != SPEC_KEYS:
        fail("schema required drifted from validator SPEC_KEYS")
    props = schema.get("properties", {})

    retrieval = props.get("retrieval_profile", {})
    if retrieval.get("additionalProperties") is not False:
        fail("schema retrieval_profile must be strict")
    if set(retrieval.get("required", [])) != RETRIEVAL_KEYS:
        fail("schema retrieval_profile.required drifted from validator RETRIEVAL_KEYS")

    memory = props.get("memory_profile", {})
    if memory.get("additionalProperties") is not False:
        fail("schema memory_profile must be strict")
    if set(memory.get("required", [])) != MEMORY_KEYS:
        fail("schema memory_profile.required drifted from validator MEMORY_KEYS")
    # The append-only provenance law cannot be optional — it is pinned in the schema too.
    if memory.get("properties", {}).get("provenance", {}).get("const") != "append_only":
        fail("schema must pin memory_profile.provenance to const 'append_only'")

    fed = props.get("federation_profile", {})
    if set(fed.get("enum", [])) != FEDERATION_MODES:
        fail("schema federation_profile.enum drifted from validator FEDERATION_MODES")


def main() -> int:
    try:
        validate_schema(load(SCHEMA))          # schema is exercised, not just parsed
        validate_genesis_seed(load(EXAMPLE))   # canonical example must pass
        for path in INVALID:
            try:
                validate_genesis_seed(load(path))
            except ValidationError:
                continue
            fail(f"expected {path.name} to be rejected, but it passed")
    except ValidationError as exc:
        print(f"ERR: {exc}", file=sys.stderr)
        return 2
    print("OK: GenesisSeed validation passed (1 example, 2 invalid rejected)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
