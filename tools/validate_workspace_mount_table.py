#!/usr/bin/env python3
"""Validate Workspace Mount Table records (A4-31, SP-ARCH-004).

The mount table is the workspace's CAPABILITY SURFACE — the complete declared set of sources pulled
back (f*) into the star's extent. Companion to A4-30 (publish = f_!). Invariants (fail-closed):

- **Zero mount authority (WS-5).** Every mount is granted by an EXTERNAL authority; `grantedBy`
  must never equal the `workspaceId` (a workspace cannot grant itself a mount).
- **No unwarranted mount.** Every entry carries a `grantRef` warrant (schema-required; re-checked).
- **The table is a set.** `sourceId`s are unique — no ambiguous double-mount of the same source.

Mirrors the schema's additionalProperties:false in the record checks (extra keys fail closed here,
not only against the JSON Schema), and exercises the schema so the two cannot silently drift —
dependency-light, matching this repo's convention (no jsonschema library).
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schemas/workspace-mount-table.schema.json"
EXAMPLE = ROOT / "examples/workspace-mount-table.example.json"
INVALID = [
    ROOT / "examples/workspace-mount-table.self-granted.invalid.json",
    ROOT / "examples/workspace-mount-table.no-grant.invalid.json",
]

META_KEYS = {"tableId", "createdAt", "labels"}
SPEC_KEYS = {"workspaceId", "declaredExtent", "entries", "policyRef", "evidenceCorrelationId"}
ENTRY_KEYS = {"sourceId", "surface", "capabilities", "grantedBy", "grantRef"}
SURFACES = {"mail", "calendar", "contacts", "drive", "docs", "sheets", "slides",
            "chat", "meeting", "admin", "audit", "policy", "search"}
CAPABILITIES = {"read", "reference", "subscribe"}


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


def no_extra(obj: dict[str, Any], allowed: set[str], ctx: str) -> None:
    extra = sorted(set(obj) - allowed)
    if extra:
        fail(f"unexpected fields in {ctx}: {extra}")


def validate_mount_table(record: Any) -> None:
    """Enforce the A4-31 invariants on one mount table. Raises ValidationError."""
    if not isinstance(record, dict):
        fail("record must be an object")
    no_extra(record, {"apiVersion", "kind", "metadata", "spec"}, "record")
    if record.get("apiVersion") != "workspace.socioprophet.dev/v1":
        fail("apiVersion mismatch")
    if record.get("kind") != "WorkspaceMountTable":
        fail("kind must be WorkspaceMountTable")

    meta = record.get("metadata")
    if not isinstance(meta, dict):
        fail("metadata must be an object")
    no_extra(meta, META_KEYS, "metadata")
    need_str(meta, "tableId")
    created = need_str(meta, "createdAt")
    try:
        datetime.fromisoformat(created.replace("Z", "+00:00"))
    except ValueError:
        fail("metadata.createdAt must be an RFC3339/ISO-8601 date-time")
    labels = meta.get("labels")
    if labels is not None and (not isinstance(labels, dict) or not all(
            isinstance(k, str) and isinstance(v, str) for k, v in labels.items())):
        fail("metadata.labels must be an object of string->string")

    spec = record.get("spec")
    if not isinstance(spec, dict):
        fail("spec must be an object")
    missing = sorted(SPEC_KEYS - set(spec))
    if missing:
        fail(f"spec missing required fields: {missing}")
    no_extra(spec, SPEC_KEYS, "spec")
    workspace_id = need_str(spec, "workspaceId")
    need_str(spec, "declaredExtent")
    need_str(spec, "policyRef")
    need_str(spec, "evidenceCorrelationId")

    entries = spec.get("entries")
    if not isinstance(entries, list) or not entries:
        fail("spec.entries must be a non-empty array")

    seen_sources: set[str] = set()
    for i, entry in enumerate(entries):
        if not isinstance(entry, dict):
            fail(f"entries[{i}] must be an object")
        no_extra(entry, ENTRY_KEYS, f"entries[{i}]")
        source_id = need_str(entry, "sourceId")
        # The table is a SET — a source may be mounted at most once (no ambiguous double-mount).
        if source_id in seen_sources:
            fail(f"entries[{i}]: sourceId {source_id!r} mounted more than once (the surface is a set)")
        seen_sources.add(source_id)

        if entry.get("surface") not in SURFACES:
            fail(f"entries[{i}].surface must be one of {sorted(SURFACES)}")
        caps = entry.get("capabilities")
        if not isinstance(caps, list) or not caps or any(c not in CAPABILITIES for c in caps):
            fail(f"entries[{i}].capabilities must be a non-empty subset of {sorted(CAPABILITIES)}")

        granted_by = need_str(entry, "grantedBy")
        # WS-5: a workspace can NEVER grant itself a mount — the authority must be external.
        if granted_by == workspace_id:
            fail(f"entries[{i}]: WS-5 violated — grantedBy equals workspaceId (self-granted mount)")
        # No unwarranted mount: every entry carries a grantRef warrant.
        need_str(entry, "grantRef")


def validate_schema(schema: Any) -> None:
    """Exercise the published schema and assert it stays in lockstep with this validator's
    invariants, so the two cannot silently drift (dependency-light, per repo convention)."""
    if not isinstance(schema, dict):
        fail("schema must be an object")
    if schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
        fail("schema must use JSON Schema draft 2020-12")
    if schema.get("additionalProperties") is not False:
        fail("schema root must be strict (additionalProperties:false)")
    props = schema.get("properties", {})
    if props.get("kind", {}).get("const") != "WorkspaceMountTable":
        fail("schema kind const mismatch")
    spec = props.get("spec", {})
    if spec.get("additionalProperties") is not False:
        fail("schema spec must be strict")
    if set(spec.get("required", [])) != SPEC_KEYS:
        fail("schema spec.required drifted from validator SPEC_KEYS")
    entry = spec.get("properties", {}).get("entries", {}).get("items", {})
    if entry.get("additionalProperties") is not False:
        fail("schema entry must be strict")
    if set(entry.get("required", [])) != ENTRY_KEYS:
        fail("schema entry.required drifted from validator ENTRY_KEYS")
    # grantedBy + grantRef must be schema-required — the WS-5/warrant invariants can't be optional.
    for req in ("grantedBy", "grantRef"):
        if req not in entry.get("required", []):
            fail(f"schema entry must require {req!r} (mount warrant/authority cannot be optional)")


def main() -> int:
    try:
        validate_schema(load(SCHEMA))          # schema is exercised, not just parsed
        validate_mount_table(load(EXAMPLE))    # canonical example must pass
        for path in INVALID:
            try:
                validate_mount_table(load(path))
            except ValidationError:
                continue
            fail(f"expected {path.name} to be rejected, but it passed")
    except ValidationError as exc:
        print(f"ERR: {exc}", file=sys.stderr)
        return 2
    print("OK: WorkspaceMountTable validation passed (1 example, 2 invalid rejected)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
