#!/usr/bin/env python3
"""Validate the labor-request contract: schema shape + request-centric chain teeth (prophet-workspace#108).

Two layers of teeth, both exercised in CI:
  1. SHAPE — every object in each example bundle validates against its `contracts/labor/*.schema.json`
     (stdlib-only JSON Schema subset: const/enum/type/required/properties/additionalProperties/items/
     pattern/minItems/minLength/minimum/maximum/uniqueItems/$ref).
  2. CHAIN — the valid bundle, run through the receipt spine (run_labor_loop), VERIFIES; every
     *.invalid.json bundle is REJECTED at the shape or the chain layer (feed/vanity model rejected).

The authoritative cross-object teeth live in tools/labor-request-contract/labor_contract.py; this
validator drives them from the declarative examples so the contract and its teeth cannot drift.
"""
from __future__ import annotations

import json
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = ROOT / "contracts/labor"
EXAMPLE_DIR = SCHEMA_DIR / "examples"

# import the authoritative chain teeth
sys.path.insert(0, str(ROOT / "tools/labor-request-contract"))
from labor_contract import (  # noqa: E402
    Evidence, Fulfillment, LaborChain, LaborContractError, LaborRequest, LaborResponse, TrustBinding,
    run_labor_loop, verify_labor_chain,
)

MEMBER_SCHEMA = {
    "request": "labor-request.schema.json",
    "response": "labor-response.schema.json",
    "fulfillment": "labor-fulfillment.schema.json",
    "trust": "trust-binding.schema.json",
}
EVIDENCE_SCHEMA = "labor-evidence.schema.json"


class ValidationError(Exception):
    pass


def load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as e:
        raise ValidationError(f"missing file: {path}") from e
    except json.JSONDecodeError as e:
        raise ValidationError(f"invalid JSON in {path.name}: {e}") from e


# --- schema registry (for $ref resolution) ---------------------------------------------------------
_REGISTRY: dict[str, dict] = {}


def _register_schemas() -> None:
    for p in SCHEMA_DIR.glob("*.schema.json"):
        s = load_json(p)
        if "$id" in s:
            _REGISTRY[s["$id"]] = s


def _resolve(schema: dict) -> dict:
    ref = schema.get("$ref")
    if ref and ref in _REGISTRY:
        return _REGISTRY[ref]
    return schema


def _type_name(v) -> str:
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "boolean"
    if isinstance(v, int):
        return "integer"
    if isinstance(v, float):
        return "number"
    if isinstance(v, str):
        return "string"
    if isinstance(v, list):
        return "array"
    if isinstance(v, dict):
        return "object"
    return type(v).__name__


def _type_ok(v, expected) -> bool:
    actual = _type_name(v)
    if expected == "number":
        return actual in {"integer", "number"}
    return actual == expected


def validate(schema: dict, value, path: str = "$") -> None:
    schema = _resolve(schema)

    if "const" in schema and value != schema["const"]:
        raise ValidationError(f"{path}: expected const {schema['const']!r}, got {value!r}")
    if "enum" in schema and value not in schema["enum"]:
        raise ValidationError(f"{path}: {value!r} not in enum {schema['enum']!r}")

    t = schema.get("type")
    if t is not None:
        types = t if isinstance(t, list) else [t]
        if not any(_type_ok(value, x) for x in types):
            raise ValidationError(f"{path}: expected type {types!r}, got {_type_name(value)!r}")

    if isinstance(value, str):
        pat = schema.get("pattern")
        if pat and not re.search(pat, value):
            raise ValidationError(f"{path}: {value!r} does not match pattern {pat!r}")
        if "minLength" in schema and len(value) < schema["minLength"]:
            raise ValidationError(f"{path}: shorter than minLength {schema['minLength']}")

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            raise ValidationError(f"{path}: {value} < minimum {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            raise ValidationError(f"{path}: {value} > maximum {schema['maximum']}")

    if isinstance(value, dict):
        for key in schema.get("required", []):
            if key not in value:
                raise ValidationError(f"{path}: missing required property {key!r}")
        props = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            extra = sorted(set(value) - set(props))
            if extra:
                raise ValidationError(f"{path}: unexpected properties {extra!r}")
        addl = schema.get("additionalProperties")
        for key, item in value.items():
            child = props.get(key)
            if child is None and isinstance(addl, dict):
                child = addl
            if child is not None:
                validate(child, item, f"{path}.{key}")

    if isinstance(value, list):
        if "minItems" in schema and len(value) < schema["minItems"]:
            raise ValidationError(f"{path}: fewer than minItems {schema['minItems']}")
        if schema.get("uniqueItems") and len(value) != len({json.dumps(x, sort_keys=True) for x in value}):
            raise ValidationError(f"{path}: items are not unique")
        item_schema = schema.get("items")
        if item_schema is not None:
            for i, item in enumerate(value):
                validate(item_schema, item, f"{path}[{i}]")


# --- bundle -> LaborChain --------------------------------------------------------------------------
def validate_shape(bundle: dict, name: str) -> None:
    for key, schema_file in MEMBER_SCHEMA.items():
        validate(load_json(SCHEMA_DIR / schema_file), bundle[key], f"{name}.{key}")
    for i, ev in enumerate(bundle.get("evidence", [])):
        validate(load_json(SCHEMA_DIR / EVIDENCE_SCHEMA), ev, f"{name}.evidence[{i}]")


def to_chain(bundle: dict) -> LaborChain:
    rq = bundle["request"]
    rs = bundle["response"]
    fl = bundle["fulfillment"]
    tr = bundle["trust"]
    return LaborChain(
        request=LaborRequest(
            request_id=rq["request_id"], requester=rq["requester"], request_type=rq["request_type"],
            objective=rq["objective"], compensation_disclosed=rq["compensation_disclosed"],
            schedule=rq["schedule"], deadline=rq["deadline"],
            evaluation_criteria=rq["evaluation_criteria"], comp_exempt=rq.get("comp_exempt", False)),
        response=LaborResponse(
            response_id=rs["response_id"], request_ref=rs["request_ref"], responder=rs["responder"],
            approach=rs["approach"], terms=rs["terms"], proposed_pricing=rs["proposed_pricing"],
            is_team_bid=rs.get("is_team_bid", False)),
        evidence=[Evidence(
            evidence_id=e["evidence_id"], response_ref=e["response_ref"], artifact_refs=e["artifact_refs"],
            evidence_grade=e["evidence_grade"], null_hypothesis_ids=e.get("null_hypothesis_ids", []))
            for e in bundle.get("evidence", [])],
        fulfillment=Fulfillment(
            fulfillment_id=fl["fulfillment_id"], award_ref=fl["award_ref"],
            evidence_refs=fl["evidence_refs"], milestones=fl["milestones"],
            completion_status=fl["completion_status"]),
        trust=TrustBinding(
            trust_id=tr["trust_id"], subject=tr["subject"], fulfillment_ref=tr["fulfillment_ref"],
            event_type=tr["event_type"], standing_ref=tr["standing_ref"], extra=tr.get("extra", {})),
    )


def run_chain(bundle: dict, ledger: Path) -> None:
    """Receipt every stage on the spine, then verify the request-centric loop."""
    chain = to_chain(bundle)
    run_labor_loop(chain, ledger)
    verify_labor_chain(chain, ledger)


def main() -> int:
    _register_schemas()
    fails = 0

    # 1) valid bundle: shape ok AND chain verifies
    valid = load_json(EXAMPLE_DIR / "labor-chain.valid.json")
    try:
        validate_shape(valid, "labor-chain.valid")
        with tempfile.TemporaryDirectory() as d:
            run_chain(valid, Path(d) / "spine.jsonl")
        print("ok: labor-chain.valid.json — shape valid AND request-centric loop verifies")
    except (ValidationError, LaborContractError) as e:
        print(f"ERR: labor-chain.valid.json should VERIFY but was rejected: {e}", file=sys.stderr)
        fails += 1

    # 2) every invalid bundle must be REJECTED at the shape or the chain layer
    for p in sorted(EXAMPLE_DIR.glob("*.invalid.json")):
        bundle = load_json(p)
        rejected_by = None
        try:
            validate_shape(bundle, p.stem)
        except ValidationError as e:
            rejected_by = f"shape: {e}"
        if rejected_by is None:
            try:
                with tempfile.TemporaryDirectory() as d:
                    run_chain(bundle, Path(d) / "spine.jsonl")
            except LaborContractError as e:
                rejected_by = f"chain: {e.code}"
        if rejected_by is None:
            print(f"ERR: {p.name} should be REJECTED but VERIFIED", file=sys.stderr)
            fails += 1
        else:
            print(f"ok: {p.name} — rejected ({rejected_by})")

    # 3) run the module's own conformance suite (teeth both ways)
    print("\n-- labor_contract teeth (tools/labor-request-contract/tests) --")
    import subprocess
    r = subprocess.run(
        [sys.executable, str(ROOT / "tools/labor-request-contract/tests/labor_contract_test.py")],
        capture_output=True, text=True)
    sys.stdout.write(r.stdout)
    if r.returncode != 0:
        sys.stderr.write(r.stderr)
        fails += 1

    if fails:
        print(f"\nLabor-request contract validation FAILED ({fails} problem(s))", file=sys.stderr)
        return 2
    print("\nLabor-request contract validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
