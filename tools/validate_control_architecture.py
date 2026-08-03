#!/usr/bin/env python3
"""Validate a ControlArchitectureDeclaration against the NIST RCS / 4D-RCS
control-architecture-of-record (ADR-0003).

The estate names the six 4D-RCS control nodes as its canonical control vocabulary.
A declaration binds each node to a real estate mechanism. This validator is the
conformance check *with teeth* — a single dependency-light file (no jsonschema
library, no new tools/ module), matching this repo's validator convention.

Teeth (fail-closed):

- **T1 — shape.** apiVersion/kind are pinned; metadata.referenceArchitecture must
  be "NIST-RCS-4D"; no unexpected fields anywhere (mirrors the schema's
  additionalProperties:false so extra keys fail here, not only against the schema).
- **T2 — all six nodes present.** The declaration MUST name all six canonical RCS
  control nodes: ValueJudgment, WorldModel, KnowledgeDatabase, SensoryRecognition,
  TaskPlanner, TaskExecutor. A declaration missing any node is REJECTED.
- **T3 — no dangling mechanism_ref.** Every node's mechanismRef MUST resolve to an
  entry in spec.mechanisms, and every mechanism MUST carry a non-empty repo/ref/kind.
  A node bound to an unknown mechanism (a dangling ref) is REJECTED.

The validator also exercises the published schema and asserts it stays in lockstep
with these invariants, so the two cannot silently drift.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schemas/control-architecture-declaration.schema.json"
EXAMPLE = ROOT / "examples/control-architecture-declaration.example.json"
INVALID = [
    ROOT / "examples/control-architecture-declaration.missing-node.invalid.json",
    ROOT / "examples/control-architecture-declaration.dangling-ref.invalid.json",
]

# The six canonical 4D-RCS control nodes (ADR-0003 §2). This set is the vocabulary.
RCS_NODES = {
    "ValueJudgment",
    "WorldModel",
    "KnowledgeDatabase",
    "SensoryRecognition",
    "TaskPlanner",
    "TaskExecutor",
}
META_KEYS = {"declarationId", "createdAt", "referenceArchitecture", "adrRef", "labels"}
META_REQUIRED = {"declarationId", "createdAt", "referenceArchitecture", "adrRef"}
SPEC_KEYS = {"mechanisms", "nodes"}
MECHANISM_KEYS = {"repo", "ref", "kind", "crossRefs"}
MECHANISM_REQUIRED = {"repo", "ref", "kind"}
NODE_KEYS = {"mechanismRef", "rcsRole"}


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


def validate_declaration(record: Any) -> None:
    """Enforce the ADR-0003 conformance invariants. Raises ValidationError."""
    if not isinstance(record, dict):
        fail("record must be an object")
    no_extra(record, {"apiVersion", "kind", "metadata", "spec"}, "record")

    # T1 — shape.
    if record.get("apiVersion") != "workspace.socioprophet.dev/v1":
        fail("apiVersion mismatch")
    if record.get("kind") != "ControlArchitectureDeclaration":
        fail("kind must be ControlArchitectureDeclaration")

    meta = record.get("metadata")
    if not isinstance(meta, dict):
        fail("metadata must be an object")
    no_extra(meta, META_KEYS, "metadata")
    missing_meta = sorted(META_REQUIRED - set(meta))
    if missing_meta:
        fail(f"metadata missing required fields: {missing_meta}")
    need_str(meta, "declarationId", "metadata")
    created = need_str(meta, "createdAt", "metadata")
    try:
        datetime.fromisoformat(created.replace("Z", "+00:00"))
    except ValueError:
        fail("metadata.createdAt must be an RFC3339/ISO-8601 date-time")
    if meta.get("referenceArchitecture") != "NIST-RCS-4D":
        fail("metadata.referenceArchitecture must be 'NIST-RCS-4D' (ADR-0003)")
    need_str(meta, "adrRef", "metadata")
    labels = meta.get("labels")
    if labels is not None:
        if not isinstance(labels, dict) or not all(
            isinstance(k, str) and isinstance(v, str) for k, v in labels.items()
        ):
            fail("metadata.labels must be an object of string->string")

    spec = record.get("spec")
    if not isinstance(spec, dict):
        fail("spec must be an object")
    no_extra(spec, SPEC_KEYS, "spec")

    mechanisms = spec.get("mechanisms")
    if not isinstance(mechanisms, dict) or not mechanisms:
        fail("spec.mechanisms must be a non-empty object")
    for ref, mech in mechanisms.items():
        ctx = f"spec.mechanisms[{ref}]"
        if not isinstance(mech, dict):
            fail(f"{ctx} must be an object")
        no_extra(mech, MECHANISM_KEYS, ctx)
        missing_mech = sorted(MECHANISM_REQUIRED - set(mech))
        if missing_mech:
            fail(f"{ctx} missing required fields: {missing_mech}")
        need_str(mech, "repo", ctx)
        need_str(mech, "ref", ctx)
        need_str(mech, "kind", ctx)
        cross = mech.get("crossRefs")
        if cross is not None:
            if not isinstance(cross, list) or not all(
                isinstance(c, str) and c for c in cross
            ):
                fail(f"{ctx}.crossRefs must be a list of non-empty strings")

    nodes = spec.get("nodes")
    if not isinstance(nodes, dict):
        fail("spec.nodes must be an object")

    # T2 — all six canonical RCS nodes must be present, and no others.
    missing_nodes = sorted(RCS_NODES - set(nodes))
    if missing_nodes:
        fail(
            "RCS conformance violated: declaration missing control node(s): "
            f"{missing_nodes} (all six 4D-RCS nodes are required)"
        )
    unknown_nodes = sorted(set(nodes) - RCS_NODES)
    if unknown_nodes:
        fail(f"unknown control node(s) not in the RCS vocabulary: {unknown_nodes}")

    # T3 — every node binds to a resolvable mechanism (no dangling ref).
    for name in sorted(RCS_NODES):
        node = nodes.get(name)
        ctx = f"spec.nodes.{name}"
        if not isinstance(node, dict):
            fail(f"{ctx} must be an object")
        no_extra(node, NODE_KEYS, ctx)
        mech_ref = need_str(node, "mechanismRef", ctx)
        need_str(node, "rcsRole", ctx)
        if mech_ref not in mechanisms:
            fail(
                f"dangling mechanism_ref: {ctx}.mechanismRef='{mech_ref}' "
                "does not resolve to any entry in spec.mechanisms"
            )


def validate_schema(schema: Any) -> None:
    """Exercise the published schema and assert it stays in lockstep with this
    validator's invariants (dependency-light: no jsonschema library, matching this
    repo's convention)."""
    if not isinstance(schema, dict):
        fail("schema must be an object")
    if schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
        fail("schema must use JSON Schema draft 2020-12")
    if schema.get("additionalProperties") is not False:
        fail("schema root must be strict (additionalProperties:false)")
    props = schema.get("properties", {})
    if props.get("kind", {}).get("const") != "ControlArchitectureDeclaration":
        fail("schema kind const mismatch")
    meta = props.get("metadata", {})
    if meta.get("properties", {}).get("referenceArchitecture", {}).get("const") != "NIST-RCS-4D":
        fail("schema must pin metadata.referenceArchitecture const 'NIST-RCS-4D'")
    spec = props.get("spec", {})
    nodes = spec.get("properties", {}).get("nodes", {})
    if nodes.get("additionalProperties") is not False:
        fail("schema spec.nodes must be strict (additionalProperties:false)")
    # The six-node requirement must be encoded in the schema itself, not only here.
    if set(nodes.get("required", [])) != RCS_NODES:
        fail("schema nodes.required drifted from validator RCS_NODES (all six required)")


def main() -> int:
    try:
        validate_schema(load(SCHEMA))  # schema is exercised, not just parsed
        validate_declaration(load(EXAMPLE))  # canonical example must pass
        for path in INVALID:
            try:
                validate_declaration(load(path))
            except ValidationError:
                continue
            fail(f"expected {path.name} to be rejected, but it passed")
    except ValidationError as exc:
        print(f"ERR: {exc}", file=sys.stderr)
        return 2
    print(
        "OK: ControlArchitectureDeclaration validation passed "
        "(6/6 RCS nodes bound, 1 example, 2 invalid rejected)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
