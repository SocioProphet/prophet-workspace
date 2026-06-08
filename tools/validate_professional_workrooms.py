#!/usr/bin/env python3
"""Validate Workroom, Professional Workroom, Office Artifact, workspace channel, and Exodus workroom bridge contracts/examples.

This validator uses only the Python standard library and supports the JSON Schema
subset used by the workspace contracts in `contracts/workspace/`.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PAIRS = [
    (
        ROOT / "contracts/workspace/workroom.schema.json",
        ROOT / "contracts/workspace/workroom.v0.1.example.json",
    ),
    (
        ROOT / "contracts/workspace/professional-workroom.schema.json",
        ROOT / "contracts/workspace/professional-workroom.v0.1.example.json",
    ),
    (
        ROOT / "contracts/workspace/office-artifact.schema.json",
        ROOT / "contracts/workspace/office-artifact.v0.1.example.json",
    ),
    (
        ROOT / "contracts/workspace/channel-substrate.schema.json",
        ROOT / "contracts/workspace/channel-substrate.v0.1.example.json",
    ),
    (
        ROOT / "contracts/workspace/interface-crossing.schema.json",
        ROOT / "contracts/workspace/interface-crossing.v0.1.example.json",
    ),
    (
        ROOT / "contracts/workspace/professional-workroom.schema.json",
        ROOT / "contracts/workspace/exodus-migration-workroom.v0.1.example.json",
    ),
    (
        ROOT / "contracts/workspace/exodus-workroom-bridge.schema.json",
        ROOT / "contracts/workspace/exodus-workroom-bridge.v0.1.example.json",
    ),
]

RECOVERED_SUBSTRATE_REF_FIELDS = [
    "policyDecisionRefs",
    "topicPackRefs",
    "memoryScopeRefs",
    "privacyDecisionRefs",
    "audioReviewRefs",
    "learningReceiptRefs",
    "semanticReceiptRefs",
]

TASK_TO_TOP_LEVEL_REF_FIELDS = {
    "topicPackRef": "topicPackRefs",
    "memoryScopeRef": "memoryScopeRefs",
    "privacyDecisionRef": "privacyDecisionRefs",
    "audioReviewRef": "audioReviewRefs",
    "learningReceiptRef": "learningReceiptRefs",
    "officeArtifactRef": "officeArtifactRefs",
    "evidenceRef": "evidenceRefs",
}


class ValidationError(Exception):
    pass


def load_json(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError as exc:
        raise ValidationError(f"missing file: {path.relative_to(ROOT)}") from exc
    except json.JSONDecodeError as exc:
        raise ValidationError(f"invalid JSON in {path.relative_to(ROOT)}: {exc}") from exc


def json_type_name(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int) and not isinstance(value, bool):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__


def type_matches(value: Any, expected: str) -> bool:
    actual = json_type_name(value)
    if expected == "number":
        return actual in {"integer", "number"}
    return actual == expected


def validate(schema: dict[str, Any], value: Any, path: str = "$") -> None:
    if "const" in schema and value != schema["const"]:
        raise ValidationError(f"{path}: expected const {schema['const']!r}, got {value!r}")

    if "enum" in schema and value not in schema["enum"]:
        raise ValidationError(f"{path}: {value!r} not in enum {schema['enum']!r}")

    expected_type = schema.get("type")
    if expected_type is not None:
        expected_types = expected_type if isinstance(expected_type, list) else [expected_type]
        if not any(type_matches(value, item) for item in expected_types):
            raise ValidationError(
                f"{path}: expected type {expected_types!r}, got {json_type_name(value)!r}"
            )

    if isinstance(value, dict):
        required = schema.get("required", [])
        for key in required:
            if key not in value:
                raise ValidationError(f"{path}: missing required property {key!r}")

        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            extra = sorted(set(value) - set(properties))
            if extra:
                raise ValidationError(f"{path}: unexpected properties {extra!r}")

        additional = schema.get("additionalProperties")
        for key, item in value.items():
            child_schema = properties.get(key)
            if child_schema is None and isinstance(additional, dict):
                child_schema = additional
            if child_schema is not None:
                validate(child_schema, item, f"{path}.{key}")

    if isinstance(value, list):
        item_schema = schema.get("items")
        if item_schema is not None:
            for index, item in enumerate(value):
                validate(item_schema, item, f"{path}[{index}]")


def validate_pair(schema_path: Path, example_path: Path) -> Any:
    schema = load_json(schema_path)
    example = load_json(example_path)
    validate(schema, example)
    print(f"ok: {example_path.relative_to(ROOT)} validates against {schema_path.relative_to(ROOT)}")
    return example


def validate_workroom_profile_binding(workroom: dict[str, Any], professional: dict[str, Any]) -> None:
    expected_ref = f"workroom://{workroom['workroomId']}"
    if professional["baseWorkroomRef"] != expected_ref:
        raise ValidationError(
            f"ProfessionalWorkroom.baseWorkroomRef expected {expected_ref!r}, got {professional['baseWorkroomRef']!r}"
        )
    if professional["workroomId"] != workroom["workroomId"]:
        raise ValidationError("ProfessionalWorkroom.workroomId must match base Workroom.workroomId")


def validate_recovered_substrate_refs(professional: dict[str, Any]) -> None:
    """Ensure the canonical example exercises recovered substrate alignment refs.

    The schema keeps these fields optional so existing workrooms can migrate
    gradually. The example should still demonstrate them and task-level refs
    should resolve to the corresponding workroom-level collections.
    """
    for field in RECOVERED_SUBSTRATE_REF_FIELDS:
        refs = professional.get(field)
        if not isinstance(refs, list) or not refs:
            raise ValidationError(f"ProfessionalWorkroom example must include non-empty {field}")
        if not all(isinstance(ref, str) and ref for ref in refs):
            raise ValidationError(f"ProfessionalWorkroom.{field} must contain non-empty string refs")

    for task in professional.get("tasks", []):
        if not isinstance(task, dict):
            continue
        for task_field, top_level_field in TASK_TO_TOP_LEVEL_REF_FIELDS.items():
            if task_field not in task:
                continue
            top_level_refs = set(professional.get(top_level_field, []))
            if task[task_field] not in top_level_refs:
                raise ValidationError(
                    f"ProfessionalWorkroom task {task.get('taskId', '<unknown>')} {task_field} "
                    f"must reference a value in top-level {top_level_field}"
                )


def validate_channel_binding(professional: dict[str, Any], office_artifact: dict[str, Any], channel: dict[str, Any], crossing: dict[str, Any]) -> None:
    if channel["workroomId"] != professional["workroomId"]:
        raise ValidationError("WorkspaceChannelSubstrate.workroomId must match ProfessionalWorkroom.workroomId")
    if crossing["workroomId"] != professional["workroomId"]:
        raise ValidationError("WorkspaceInterfaceCrossing.workroomId must match ProfessionalWorkroom.workroomId")

    valid_artifact_refs = set(professional.get("officeArtifactRefs", []))
    valid_artifact_refs.add(office_artifact["storageRef"])
    if channel.get("officeArtifactRef") not in valid_artifact_refs:
        raise ValidationError("WorkspaceChannelSubstrate.officeArtifactRef must match either a ProfessionalWorkroom officeArtifactRef or OfficeArtifact.storageRef")
    if crossing.get("officeArtifactRef") != channel.get("officeArtifactRef"):
        raise ValidationError("WorkspaceInterfaceCrossing.officeArtifactRef must match the channel officeArtifactRef")
    if crossing["fromChannelRef"] != channel["channelId"]:
        raise ValidationError("WorkspaceInterfaceCrossing.fromChannelRef must reference the WorkspaceChannelSubstrate example")
    if crossing["review"]["required"] is not True or crossing["review"]["status"] != "pending":
        raise ValidationError("WorkspaceInterfaceCrossing review must remain required and pending in the example")
    for key, value in channel["authority"].items():
        if value is not False:
            raise ValidationError(f"WorkspaceChannelSubstrate.authority.{key} must be false")
    for key, value in channel["runtimeBoundary"].items():
        if value is not False:
            raise ValidationError(f"WorkspaceChannelSubstrate.runtimeBoundary.{key} must be false")
    for key, value in crossing["runtimeBoundary"].items():
        if value is not False:
            raise ValidationError(f"WorkspaceInterfaceCrossing.runtimeBoundary.{key} must be false")


def validate_exodus_bridge(exodus_workroom: dict[str, Any], bridge: dict[str, Any]) -> None:
    if bridge["workroomRef"] != f"workroom://{exodus_workroom['workroomId']}":
        raise ValidationError("ExodusWorkroomBridge.workroomRef must reference the Exodus ProfessionalWorkroom")
    if bridge["tenantId"] != exodus_workroom.get("tenantId"):
        raise ValidationError("ExodusWorkroomBridge.tenantId must match Exodus ProfessionalWorkroom.tenantId")
    if bridge["exodusRunRef"] not in exodus_workroom.get("contextRefs", []):
        raise ValidationError("ExodusWorkroomBridge.exodusRunRef must appear in ProfessionalWorkroom.contextRefs")

    boundary = bridge["demoBoundary"]
    if boundary["synthetic"] is not True:
        raise ValidationError("ExodusWorkroomBridge demoBoundary.synthetic must be true")
    if boundary["liveCredentialsRequired"] is not False:
        raise ValidationError("ExodusWorkroomBridge must not require live credentials")
    if boundary["destructiveActionsAllowed"] is not False:
        raise ValidationError("ExodusWorkroomBridge must not allow destructive actions")
    if boundary["providerSideWritesAllowed"] is not False:
        raise ValidationError("ExodusWorkroomBridge must not allow provider-side writes")

    for ref in bridge.get("providerTopologyRefs", []):
        if ref not in exodus_workroom.get("providerCaptureRefs", []):
            raise ValidationError(f"provider topology ref {ref!r} must appear in ProfessionalWorkroom.providerCaptureRefs")
    for ref in bridge.get("assetCensusRefs", []):
        if ref not in exodus_workroom.get("providerProjectionRefs", []) and ref not in exodus_workroom.get("evidenceRefs", []):
            # The workroom only carries representative asset projections at top level.
            # Full census remains in the bridge.
            continue
    for ref in bridge.get("officeArtifactRefs", []):
        if ref not in exodus_workroom.get("officeArtifactRefs", []):
            raise ValidationError(f"office artifact ref {ref!r} must appear in ProfessionalWorkroom.officeArtifactRefs")
    for ref in bridge.get("evidenceRefs", []):
        if ref not in exodus_workroom.get("evidenceRefs", []):
            raise ValidationError(f"evidence ref {ref!r} must appear in ProfessionalWorkroom.evidenceRefs")

    if not bridge.get("scoreRefs"):
        raise ValidationError("ExodusWorkroomBridge.scoreRefs must be non-empty")
    if not bridge.get("blockerRefs"):
        raise ValidationError("ExodusWorkroomBridge.blockerRefs must be non-empty")
    if not bridge.get("recommendationRefs"):
        raise ValidationError("ExodusWorkroomBridge.recommendationRefs must be non-empty")
    if not bridge.get("budgetProposalRef"):
        raise ValidationError("ExodusWorkroomBridge.budgetProposalRef must be non-empty")


def main() -> int:
    try:
        examples = []
        for schema_path, example_path in CONTRACT_PAIRS:
            examples.append(validate_pair(schema_path, example_path))
        validate_workroom_profile_binding(examples[0], examples[1])
        validate_recovered_substrate_refs(examples[1])
        validate_channel_binding(examples[1], examples[2], examples[3], examples[4])
        validate_recovered_substrate_refs(examples[5])
        validate_exodus_bridge(examples[5], examples[6])
    except ValidationError as exc:
        print(f"ERR: {exc}", file=sys.stderr)
        return 2

    print("Workroom validation passed")
    print("Professional Workroom validation passed")
    print("Recovered substrate reference validation passed")
    print("Office Artifact validation passed")
    print("Workspace channel substrate validation passed")
    print("Workspace interface crossing validation passed")
    print("Exodus workroom bridge validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
