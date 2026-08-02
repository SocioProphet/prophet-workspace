#!/usr/bin/env python3
"""Validate SP-File Naming decision records (A4-30, SP-ARCH-004 §8).

The SP-File Naming agent is the reference implementation of the workspace as a
star machine. Invariants enforced here (fail-closed):

- **Zero mount authority (WS-5).** The agent cannot widen its reach; mountAuthority
  must be "none".
- **Filing is publish (f_!).** The operation must be "publish"; mounting/restricting
  is not a filing decision.
- **The decision is a checkable artifact.** A publish must carry a ProofArtifact
  (a sha256 outputDigest + a publicationRef).
- **Narrow declared extent.** The agent's extent must be declared and non-empty.

Also mirrors the schema's additionalProperties:false in the record checks so extra
keys fail closed here, not only against the JSON Schema.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schemas/sp-file-naming-decision.schema.json"
EXAMPLE = ROOT / "examples/sp-file-naming-decision.example.json"
INVALID = [
    ROOT / "examples/sp-file-naming-decision.mount-widen.invalid.json",
    ROOT / "examples/sp-file-naming-decision.not-publish.invalid.json",
]

META_KEYS = {"decisionId", "createdAt", "labels"}
SPEC_KEYS = {
    "agentId",
    "declaredExtent",
    "mountAuthority",
    "operation",
    "inputArtifactId",
    "canonicalName",
    "targetPath",
    "proofArtifact",
    "policyRef",
    "evidenceCorrelationId",
}
PROOF_KEYS = {"outputDigest", "publicationRef", "inclusionRecord"}


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


def validate_decision(record: Any) -> None:
    """Enforce the A4-30 invariants on one decision record. Raises ValidationError."""
    if not isinstance(record, dict):
        fail("record must be an object")
    no_extra(record, {"apiVersion", "kind", "metadata", "spec"}, "record")
    if record.get("apiVersion") != "workspace.socioprophet.dev/v1":
        fail("apiVersion mismatch")
    if record.get("kind") != "SpFileNamingDecision":
        fail("kind must be SpFileNamingDecision")

    meta = record.get("metadata")
    if not isinstance(meta, dict):
        fail("metadata must be an object")
    no_extra(meta, META_KEYS, "metadata")
    need_str(meta, "decisionId")
    need_str(meta, "createdAt")

    spec = record.get("spec")
    if not isinstance(spec, dict):
        fail("spec must be an object")
    missing = sorted(SPEC_KEYS - set(spec))
    if missing:
        fail(f"spec missing required fields: {missing}")
    no_extra(spec, SPEC_KEYS, "spec")

    need_str(spec, "agentId")
    need_str(spec, "declaredExtent")  # narrow extent must be declared
    need_str(spec, "inputArtifactId")
    need_str(spec, "canonicalName")
    need_str(spec, "targetPath")
    need_str(spec, "policyRef")
    need_str(spec, "evidenceCorrelationId")

    # WS-5: the SP-File Naming agent has zero mount authority.
    if spec.get("mountAuthority") != "none":
        fail("WS-5 violated: SP-File Naming agent must have mountAuthority 'none'")

    # Filing is a publish (f_!), not a mount or restrict.
    if spec.get("operation") != "publish":
        fail("A4-30 violated: filing operation must be 'publish'")

    # A publish must carry a ProofArtifact — the decision is a checkable artifact.
    proof = spec.get("proofArtifact")
    if not isinstance(proof, dict):
        fail("proofArtifact must be an object")
    no_extra(proof, PROOF_KEYS, "proofArtifact")
    digest = need_str(proof, "outputDigest")
    if not (digest.startswith("sha256:") and len(digest) == len("sha256:") + 64):
        fail("proofArtifact.outputDigest must be a sha256 digest")
    need_str(proof, "publicationRef")


def main() -> int:
    try:
        load(SCHEMA)  # must be valid JSON
        validate_decision(load(EXAMPLE))  # canonical example must pass
        for path in INVALID:
            try:
                validate_decision(load(path))
            except ValidationError:
                continue
            fail(f"expected {path.name} to be rejected, but it passed")
    except ValidationError as exc:
        print(f"ERR: {exc}", file=sys.stderr)
        return 2
    print("OK: SpFileNamingDecision validation passed (1 example, 2 invalid rejected)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
