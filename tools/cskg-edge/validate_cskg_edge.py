#!/usr/bin/env python3
"""Validate CSKGEdge records — the governance-bearing edge the cypher-atomspace-gateway (WO-A) can consume.

The gateway today carries only a bare TruthValue{strength,confidence} per CSKG edge (see
`tools/cypher-atomspace-gateway/adapter.py`). The Masonmark "Schema-Grounded KAIROS/CHRONOS CSKG" deck
(slide 54, "Ontology Grounding + Commonsense Priors") is blunt: CSKG/ConceptNet commonsense is
*defeasible support*, never institutional truth. This validator makes that law mechanical on the edge,
and restores two things the gateway fixture dropped: public-CSKG provenance (source/sentence) and
temporal typing.

The teeth (cross-field rules a pure schema states but this validator ENFORCES, both ways):

- **CE-T1  commonsense is defeasible** — `epistemicTier=commonsense` REQUIRES `defeasible=true`.
  A commonsense edge can never be authoritative (deck slide 54; the core rule).
- **CE-T2  institutional is authoritative** — `epistemicTier=institutional` REQUIRES `defeasible=false`.
  Institutional truth is not overridable by a commonsense prior.
- **CE-T3  provenance-complete** — institutional & schema tiers REQUIRE `provenance.source`
  (deck slides 53/54: promoted artifacts bind to governed ids + source, not raw strings).
- **CE-T4  truth in range** — `truth.strength` and `truth.confidence` in [0,1] (the gateway's TruthValue).
- **CE-T5  valid-interval well-formed** — when both present, `validFromMicros <= validToMicros`.
- **CE-T6  authority requires promotion** — a non-defeasible (authoritative) edge MUST be `status=promoted`.
  A `candidate` (cairnmark) or `tombstoned` edge cannot authorize (cairnmark -> Stele gate).
- **CE-T7  no transaction clock on the edge** — `temporal` accepts valid-time + observation-time ONLY.
  Transaction/system-time (`txn_created`) stays on the record/ledger (metadata-record three-time model +
  proof-artifact spine). This is why the deck's "Kairos/Chronos" framing adds no new clock: the
  event-vs-system distinction is already the estate three-time model; the edge only needs valid+observed.

Dependency-light (no jsonschema library), matching this repo's convention. The schema is *exercised*
(`validate_schema`) so the published JSON Schema and these Python teeth cannot silently drift.
Run: `python3 tools/cskg-edge/validate_cskg_edge.py`
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
SCHEMA = ROOT / "schemas/cskg-edge.schema.json"
EXAMPLES = ROOT / "examples"

RECORD_KEYS = {"apiVersion", "kind", "metadata", "spec"}
META_KEYS = {"edgeId", "createdAt", "labels"}
SPEC_KEYS = {"node1", "relation", "node2", "lifted", "truth", "epistemicTier",
             "defeasible", "status", "provenance", "temporal"}
SPEC_REQUIRED = {"node1", "relation", "node2", "truth", "epistemicTier", "defeasible", "status"}
TRUTH_KEYS = {"strength", "confidence"}
PROV_KEYS = {"source", "sentence", "extractor"}
TEMPORAL_KEYS = {"validFromMicros", "validToMicros", "observedAtMicros"}
LIFTED_KEYS = {"node1Label", "node2Label", "relationLabel", "relationDimension"}
TIERS = {"institutional", "schema", "commonsense"}
STATUSES = {"candidate", "promoted", "tombstoned"}


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


def _unit(obj: dict[str, Any], key: str, ctx: str) -> None:
    v = obj.get(key)
    # bool is an int subclass; reject it explicitly so `true` can't sneak in as 1.
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        fail(f"{ctx}.{key}: expected number in [0,1]")
    if not (0.0 <= float(v) <= 1.0):
        fail(f"{ctx}.{key}: {v} out of range [0,1]")  # CE-T4


def validate_cskg_edge(record: Any) -> None:
    """Enforce the CSKGEdge envelope + the seven teeth on one edge. Raises ValidationError."""
    if not isinstance(record, dict):
        fail("record must be an object")
    no_extra(record, RECORD_KEYS, "record")
    if record.get("apiVersion") != "graph.socioprophet.dev/v1":
        fail("apiVersion must be graph.socioprophet.dev/v1")
    if record.get("kind") != "CSKGEdge":
        fail("kind must be CSKGEdge")

    meta = record.get("metadata")
    if not isinstance(meta, dict):
        fail("metadata must be an object")
    no_extra(meta, META_KEYS, "metadata")
    need_str(meta, "edgeId", "metadata")
    created = need_str(meta, "createdAt", "metadata")
    try:
        datetime.fromisoformat(created.replace("Z", "+00:00"))
    except ValueError:
        fail("metadata.createdAt must be an RFC3339/ISO-8601 date-time")

    spec = record.get("spec")
    if not isinstance(spec, dict):
        fail("spec must be an object")
    missing = sorted(SPEC_REQUIRED - set(spec))
    if missing:
        fail(f"spec missing required fields: {missing}")
    no_extra(spec, SPEC_KEYS, "spec")
    need_str(spec, "node1", "spec")
    need_str(spec, "relation", "spec")
    need_str(spec, "node2", "spec")

    tier = spec.get("epistemicTier")
    if tier not in TIERS:
        fail(f"spec.epistemicTier must be one of {sorted(TIERS)}")
    defeasible = spec.get("defeasible")
    if not isinstance(defeasible, bool):
        fail("spec.defeasible must be a boolean")
    status = spec.get("status")
    if status not in STATUSES:
        fail(f"spec.status must be one of {sorted(STATUSES)}")

    # truth (CE-T4)
    truth = spec.get("truth")
    if not isinstance(truth, dict):
        fail("spec.truth must be an object")
    no_extra(truth, TRUTH_KEYS, "spec.truth")
    for k in ("strength", "confidence"):
        if k not in truth:
            fail(f"spec.truth.{k} is required")
        _unit(truth, k, "spec.truth")

    # optional structural blocks
    lifted = spec.get("lifted")
    if lifted is not None:
        if not isinstance(lifted, dict):
            fail("spec.lifted must be an object")
        no_extra(lifted, LIFTED_KEYS, "spec.lifted")

    prov = spec.get("provenance")
    if prov is not None:
        if not isinstance(prov, dict):
            fail("spec.provenance must be an object")
        no_extra(prov, PROV_KEYS, "spec.provenance")
        need_str(prov, "source", "spec.provenance")

    temporal = spec.get("temporal")
    if temporal is not None:
        if not isinstance(temporal, dict):
            fail("spec.temporal must be an object")
        # CE-T7: valid-time + observation-time only; a transaction/system clock on the edge is rejected.
        no_extra(temporal, TEMPORAL_KEYS, "spec.temporal")
        vf, vt = temporal.get("validFromMicros"), temporal.get("validToMicros")
        for k in ("validFromMicros", "validToMicros", "observedAtMicros"):
            if k in temporal and temporal[k] is not None and not isinstance(temporal[k], int):
                fail(f"spec.temporal.{k} must be an integer (unix micros) or null")
        # CE-T5: valid interval well-formed when both endpoints are present.
        if isinstance(vf, int) and isinstance(vt, int) and vf > vt:
            fail(f"spec.temporal: validFromMicros ({vf}) must be <= validToMicros ({vt})")

    # --- the authority laws (CE-T1/T2/T3/T6) ---
    if tier == "commonsense" and defeasible is not True:
        fail("CE-T1: a commonsense edge MUST be defeasible=true (commonsense is never authoritative)")
    if tier == "institutional" and defeasible is not False:
        fail("CE-T2: an institutional edge MUST be defeasible=false (institutional truth is authoritative)")
    if tier in ("institutional", "schema") and not (isinstance(prov, dict) and prov.get("source")):
        fail(f"CE-T3: {tier} tier requires provenance.source (provenance-complete by construction)")
    if defeasible is False and status != "promoted":
        fail(f"CE-T6: a non-defeasible (authoritative) edge must be status=promoted, not {status!r}")


def validate_schema(schema: Any) -> None:
    """Exercise the published schema and assert it stays in lockstep with the validator's laws, so the
    two cannot silently drift (dependency-light, per repo convention)."""
    if not isinstance(schema, dict):
        fail("schema must be an object")
    if schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
        fail("schema must use JSON Schema draft 2020-12")
    if schema.get("additionalProperties") is not False:
        fail("schema root must be strict (additionalProperties:false)")
    props = schema.get("properties", {})
    if props.get("kind", {}).get("const") != "CSKGEdge":
        fail("schema kind const mismatch")
    spec = props.get("spec", {})
    if spec.get("additionalProperties") is not False:
        fail("schema spec must be strict")
    if set(spec.get("required", [])) != SPEC_REQUIRED:
        fail("schema spec.required drifted from validator SPEC_REQUIRED")
    sp = spec.get("properties", {})
    if set(sp.get("epistemicTier", {}).get("enum", [])) != TIERS:
        fail("schema epistemicTier enum drifted from validator TIERS")
    if set(sp.get("status", {}).get("enum", [])) != STATUSES:
        fail("schema status enum drifted from validator STATUSES")
    # CE-T7 must be mechanical in the schema too: temporal is strict and carries no transaction clock.
    temporal = sp.get("temporal", {})
    if temporal.get("additionalProperties") is not False:
        fail("schema spec.temporal must be strict (CE-T7: no transaction clock on the edge)")
    if set(temporal.get("properties", {})) != TEMPORAL_KEYS:
        fail("schema spec.temporal properties drifted from validator TEMPORAL_KEYS")
    if "txn_created" in temporal.get("properties", {}) or "txnCreated" in temporal.get("properties", {}):
        fail("CE-T7: edge temporal must NOT carry a transaction/system clock (that is the record/ledger)")
    # The four authority laws (CE-T1/T2/T3/T6) must exist as if/then guards in the schema's allOf.
    branches = spec.get("allOf", [])
    if len(branches) < 4:
        fail("schema spec.allOf must encode the CE-T1/T2/T3/T6 authority laws (4 if/then guards)")


def main() -> int:
    try:
        validate_schema(load(SCHEMA))                 # schema is exercised, not just parsed
        files = sorted(EXAMPLES.glob("*.json"))
        valids = [f for f in files if f.name.endswith(".valid.json")]
        invalids = [f for f in files if f.name.endswith(".invalid.json")]
        if not valids or not invalids:
            fail("examples/ must contain both *.valid.json and *.invalid.json fixtures")
        for path in valids:
            try:
                validate_cskg_edge(load(path))
            except ValidationError as exc:
                fail(f"expected {path.name} to PASS, but it was rejected: {exc}")
        for path in invalids:
            try:
                validate_cskg_edge(load(path))
            except ValidationError:
                continue
            fail(f"expected {path.name} to be REJECTED, but it passed")
    except ValidationError as exc:
        print(f"ERR: {exc}", file=sys.stderr)
        return 2
    print(f"OK: CSKGEdge validation passed ({len(valids)} valid, {len(invalids)} invalid rejected)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
