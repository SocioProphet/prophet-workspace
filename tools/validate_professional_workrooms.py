#!/usr/bin/env python3
"""Validate Workroom, Professional Workroom, Office Artifact, and workspace channel contracts/examples.

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
]


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


def main() -> int:
    try:
        examples = []
        for schema_path, example_path in CONTRACT_PAIRS:
            examples.append(validate_pair(schema_path, example_path))
        validate_workroom_profile_binding(examples[0], examples[1])
        validate_channel_binding(examples[1], examples[2], examples[3], examples[4])
    except ValidationError as exc:
        print(f"ERR: {exc}", file=sys.stderr)
        return 2

    print("Workroom validation passed")
    print("Professional Workroom validation passed")
    print("Office Artifact validation passed")
    print("Workspace channel substrate validation passed")
    print("Workspace interface crossing validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
