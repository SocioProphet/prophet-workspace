#!/usr/bin/env python3
"""Validate AgentCognitionER — the contract, its instances, its memory binding, and the schema-drift guard.

Runs, all fail-closed (dependency-light, no jsonschema, per repo convention):
  1. the ER model self-consistency (entities/relations well-typed);
  2. the memory-type ↔ ER binding drift guard (memory_binding.validate_memory_binding);
  3. the published JSON Schema is *exercised* against the Python model — the enum lists (entity types +
     predicates) cannot silently drift from agent_cognition_er.py;
  4. every fixture in examples/ validates as declared (*.valid.json passes, *.invalid.json is REJECTED).

Run: python3 tools/agent-cognition-er/validate_agent_cognition_er.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from agent_cognition_er import (  # noqa: E402
    ENTITIES, RELATIONS, ERError, validate_er_instance,
)
from memory_binding import validate_memory_binding  # noqa: E402

SCHEMA = ROOT / "schemas/agent-cognition-er.schema.json"
EXAMPLES = ROOT / "examples"


class ValidationError(Exception):
    pass


def load(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValidationError(f"missing file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValidationError(f"invalid JSON in {path}: {exc}") from exc


def validate_schema(schema: dict) -> None:
    """Exercise the schema against the Python model so the two cannot silently drift."""
    props = schema.get("properties", {})
    ent_enum = set(props.get("entities", {}).get("propertyNames", {}).get("enum", []))
    if ent_enum != set(ENTITIES):
        raise ValidationError("schema entity enum drifted from ENTITIES: "
                              f"{ent_enum ^ set(ENTITIES)}")
    pred_enum = set(
        props.get("edges", {}).get("items", {}).get("prefixItems", [])[1].get("enum", [])
    )
    model_preds = {r.predicate for r in RELATIONS}
    if pred_enum != model_preds:
        raise ValidationError("schema predicate enum drifted from RELATIONS: "
                              f"{pred_enum ^ model_preds}")


def main() -> int:
    # 1. model well-typed (dataclass __post_init__ already checks verdicts on import)
    assert len(ENTITIES) == 17, f"expected 17 entities, got {len(ENTITIES)}"
    assert len(RELATIONS) == 18, f"expected 18 relations, got {len(RELATIONS)}"

    # 2. memory binding drift guard
    validate_memory_binding()

    # 3. schema drift guard (schema is exercised, not just parsed)
    validate_schema(load(SCHEMA))

    # 4. fixtures both ways
    valids = sorted(EXAMPLES.glob("*.valid.json"))
    invalids = sorted(EXAMPLES.glob("*.invalid.json"))
    if not valids or not invalids:
        raise ValidationError("examples/ must contain both *.valid.json and *.invalid.json fixtures")

    for path in valids:
        try:
            validate_er_instance(load(path))
        except ERError as exc:
            raise ValidationError(f"{path.name}: expected VALID but REJECTED: {exc}") from exc
        print(f"  ok    {path.name} (valid, accepted)")

    for path in invalids:
        try:
            validate_er_instance(load(path))
        except ERError:
            print(f"  ok    {path.name} (invalid, REJECTED)")
            continue
        raise ValidationError(f"{path.name}: expected REJECTED but was ACCEPTED")

    print("AgentCognitionER validation OK — model + memory-binding + schema-drift + fixtures both ways.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValidationError as exc:
        print(f"VALIDATION FAILED: {exc}", file=sys.stderr)
        raise SystemExit(1)
