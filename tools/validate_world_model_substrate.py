#!/usr/bin/env python3
"""Validate WorldModelSubstrate descriptors (ADR-0002 §4 L1 / GAP-4, pw#86).

GAP-4 asks for ONE coherent, enforceable reference for the Layer-1
temporal-topological substrate

    W = (S_dur, S_act, Theta, T, C, Pi, E)

so the doctrine that is scattered across superconscious / ProCybernetica /
three-time / the receipt spine becomes a single checkable declaration. This
validator is the teeth for that declaration. It enforces, fail-closed:

- **All seven components present.** A substrate must name every element of the
  tuple W = (S_dur, S_act, Theta, T, C, Pi, E). Missing one is rejected.
- **No unknown components.** The component set is closed; an extra key (e.g. a
  bogus "Q") is rejected (mirrors the schema's additionalProperties:false).
- **Every mechanismRef resolves AND is the right owner.** Each component and each
  structural attribute binds to an owning estate mechanism via `mechanismRef`. A
  ref outside the known-mechanism registry (below) is DANGLING and rejected; a ref
  that IS in the registry but is not the mechanism DESIGNATED for the slot citing
  it is CROSS-WIRED and rejected. The registry is a closed vocabulary of real L1
  estate mechanisms and the per-slot binding map pins each construct to its owner,
  so the check is deterministic and CI-safe (independent of which repos are checked
  out). This is what stops a Theta<->T swap, a component pointing at another's
  mechanism, or every component collapsing onto one ref.
- **The four structural attributes are declared.** Order cycle S^1 + lift tau,
  the recursive Hopf tower H0..H3, the dual-sector decomposition V+ (manifest) /
  V- (latent), and the balance observable M(Psi).

Canonical symbol assignment (the reconciliation this closes): **Theta = order
bundle** (the order structure / order cycle S^1 + lift tau) and **T = transition
algebra**. This corrects the row labels in the ADR-0002 §4 L1 table, which
described "Order structure T" and "Transition algebra Theta"; the canonical
tuple and doctrine are reconciled to Theta=order, T=transition here and in
docs/architecture/world-model-substrate.md.

Dependency-light (no jsonschema library), matching this repo's convention: the
schema is exercised and asserted to stay in lockstep with these invariants so
the two cannot silently drift.

Run: `python3 tools/validate_world_model_substrate.py`
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schemas/world-model-substrate.schema.json"
EXAMPLE = ROOT / "examples/world-model-substrate.example.json"
INVALID = [
    ROOT / "examples/world-model-substrate.missing-component.invalid.json",
    ROOT / "examples/world-model-substrate.unknown-component.invalid.json",
    ROOT / "examples/world-model-substrate.dangling-ref.invalid.json",
    ROOT / "examples/world-model-substrate.cross-wired-ref.invalid.json",
]

MECHANISM_REF_RE = re.compile(r"^estate://[A-Za-z0-9._-]+/[A-Za-z0-9._/-]+$")
VERDICTS = {"HAVE", "PARTIAL", "GAP"}

# The seven components of the World-Model substrate W = (S_dur, S_act, Theta, T, C, Pi, E).
COMPONENT_KEYS = {"S_dur", "S_act", "Theta", "T", "C", "Pi", "E"}
COMPONENT_FIELDS = {"role", "mechanismRef", "verdict", "evidence"}
COMPONENT_REQUIRED = {"role", "mechanismRef", "verdict"}

# Closed vocabulary of the estate mechanisms that own an L1 substrate binding.
# A mechanismRef NOT in this registry is "dangling" and fails closed. Each ref is
# the mechanism ADR-0002 §4 (L1) cites for that construct; keeping the vocabulary
# here (not on disk) makes the gate deterministic and independent of the checkout.
MECHANISM_REGISTRY = {
    "estate://prophet-workspace/tools/cypher-atomspace-gateway":
        "S_dur — AtomSpace canonical store behind the Cypher-subset facade (HellGraph)",
    "estate://prophet-platform/apps/regis-acr-api/src/regis_acr_api/er_spine.py":
        "S_act / T(order) — bitemporal valid_time/system_time active projection (three-time)",
    "estate://regis-entity-graph/schemas/node.schema.json":
        "S_act — bitemporal node schema (valid_time/system_time)",
    "estate://ProCybernetica/procyber/semantic/agent_coordinate_vector.py":
        "Theta — 11-axis AgentCoordinateVector carrying the order structure (semantic coordinate)",
    "estate://ProCybernetica/procyber/semantic/semantic_algebra.py":
        "Pi / orderCycle — lift dashv ground projection adjunction",
    "estate://ProCybernetica/procyber/semantic/spectral_grounding.py":
        "dualSector / balanceObservable — spectral-field math for the topological constructs",
    "estate://sp-orchestrator/crates/sp-exec/src/exec.rs":
        "T — transition operators in the orchestrator DAG",
    "estate://policy-fabric/contracts":
        "C — constraint family expressed as policy contracts",
    "estate://prophet-workspace/tools/proof-artifact-spine":
        "E — hash-chained ProofArtifact receipt spine (AC-1)",
    "estate://superconscious/docs/doctrine/semantic-address-algebra-as-spectral-field-skeleton.v0.1.md":
        "hopfTower / doctrine carrier (order cycle / Hopf / dual-sector / M(Psi))",
    "estate://superconscious/harness":
        "monodromy — falsification harness (ADR-0001 §9.7)",
}

# --- per-slot binding: which mechanism each construct is ALLOWED to cite ---
# The registry above answers "is this ref a real L1 mechanism?". That is not
# enough: a ref can be real yet be the WRONG owner for the slot citing it. The
# reconciliation this PR closes is precisely Theta = order bundle, T = transition
# algebra; if the two refs are merely "known" but interchangeable, a declaration
# that swaps them (Theta -> sp-exec, T -> agent_coordinate_vector) sails through
# and re-introduces the exact bug GAP-4 exists to kill. So each construct slot
# binds to its designated owning mechanism (a small set where the estate
# legitimately shares one file across two slots). A mechanismRef that is in the
# registry but NOT designated for the slot citing it is CROSS-WIRED and fails
# closed. This also kills the degenerate "point every component at one ref" and
# any duplicate/cross-component wiring.
COMPONENT_MECHANISMS = {
    "S_dur": {"estate://prophet-workspace/tools/cypher-atomspace-gateway"},
    "S_act": {
        "estate://prophet-platform/apps/regis-acr-api/src/regis_acr_api/er_spine.py",
        "estate://regis-entity-graph/schemas/node.schema.json",
    },
    "Theta": {"estate://ProCybernetica/procyber/semantic/agent_coordinate_vector.py"},
    "T": {"estate://sp-orchestrator/crates/sp-exec/src/exec.rs"},
    "C": {"estate://policy-fabric/contracts"},
    "Pi": {"estate://ProCybernetica/procyber/semantic/semantic_algebra.py"},
    "E": {"estate://prophet-workspace/tools/proof-artifact-spine"},
}
STRUCTURAL_MECHANISMS = {
    "spec.orderCycle": {"estate://ProCybernetica/procyber/semantic/semantic_algebra.py"},
    "spec.hopfTower": {
        "estate://superconscious/docs/doctrine/"
        "semantic-address-algebra-as-spectral-field-skeleton.v0.1.md"
    },
    "spec.dualSector": {"estate://ProCybernetica/procyber/semantic/spectral_grounding.py"},
    "spec.balanceObservable": {"estate://ProCybernetica/procyber/semantic/spectral_grounding.py"},
    "spec.monodromy": {"estate://superconscious/harness"},
}
# ctx string -> allowed refs, keyed by the ctx passed to check_mechanism_ref.
SLOT_MECHANISMS: dict[str, set[str]] = {
    **{f"components.{k}": v for k, v in COMPONENT_MECHANISMS.items()},
    **STRUCTURAL_MECHANISMS,
}


def _assert_binding_maps_consistent() -> None:
    """The binding maps must not silently drift from the registry: every bound
    ref must be a real registry mechanism, and every registry mechanism must be
    reachable from some slot (no dead entries). Fails closed on drift."""
    bound: set[str] = set()
    for ctx, refs in SLOT_MECHANISMS.items():
        for ref in refs:
            if ref not in MECHANISM_REGISTRY:
                fail(f"binding map for {ctx} cites a ref not in the registry: {ref!r}")
            bound.add(ref)
    orphan = sorted(set(MECHANISM_REGISTRY) - bound)
    if orphan:
        fail(f"registry has mechanisms bound to no slot (dead entries): {orphan}")


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


def check_mechanism_ref(ref: str, ctx: str) -> None:
    """A mechanismRef must be well-formed, resolve to a known estate mechanism,
    AND be the mechanism DESIGNATED for the slot citing it. An unknown ref is
    dangling; a known-but-wrong ref is cross-wired. Both fail closed."""
    if not MECHANISM_REF_RE.fullmatch(ref):
        fail(f"{ctx}.mechanismRef malformed (want estate://<repo>/<path>): {ref!r}")
    if ref not in MECHANISM_REGISTRY:
        fail(f"{ctx}.mechanismRef is dangling (not in the known-mechanism registry): {ref!r}")
    allowed = SLOT_MECHANISMS.get(ctx)
    if allowed is not None and ref not in allowed:
        fail(f"{ctx}.mechanismRef is cross-wired: {ref!r} is a known mechanism but is not "
             f"the one designated for {ctx} (expected one of {sorted(allowed)})")


def check_verdict(obj: dict[str, Any], ctx: str) -> None:
    v = obj.get("verdict")
    if v is not None and v not in VERDICTS:
        fail(f"{ctx}.verdict must be one of {sorted(VERDICTS)}; got {v!r}")


def check_component(name: str, comp: Any) -> None:
    ctx = f"components.{name}"
    if not isinstance(comp, dict):
        fail(f"{ctx} must be an object")
    no_extra(comp, COMPONENT_FIELDS, ctx)
    missing = sorted(COMPONENT_REQUIRED - set(comp))
    if missing:
        fail(f"{ctx} missing required fields: {missing}")
    need_str(comp, "role", ctx)
    if comp["verdict"] not in VERDICTS:
        fail(f"{ctx}.verdict must be one of {sorted(VERDICTS)}; got {comp['verdict']!r}")
    check_mechanism_ref(comp["mechanismRef"], ctx)
    if "evidence" in comp and not isinstance(comp["evidence"], str):
        fail(f"{ctx}.evidence must be a string when present")


def validate_substrate(record: Any) -> None:
    """Enforce the GAP-4 substrate invariants on one declaration. Raises ValidationError."""
    if not isinstance(record, dict):
        fail("record must be an object")
    no_extra(record, {"apiVersion", "kind", "metadata", "spec"}, "record")
    if record.get("apiVersion") != "workspace.socioprophet.dev/v1":
        fail("apiVersion mismatch")
    if record.get("kind") != "WorldModelSubstrate":
        fail("kind must be 'WorldModelSubstrate'")

    meta = record.get("metadata")
    if not isinstance(meta, dict):
        fail("metadata must be an object")
    no_extra(meta, {"substrateId", "createdAt", "labels"}, "metadata")
    need_str(meta, "substrateId", "metadata")
    need_str(meta, "createdAt", "metadata")

    spec = record.get("spec")
    if not isinstance(spec, dict):
        fail("spec must be an object")
    no_extra(spec, {"components", "orderCycle", "hopfTower", "dualSector",
                    "balanceObservable", "monodromy"}, "spec")

    # --- the seven components: exactly S_dur, S_act, Theta, T, C, Pi, E ---
    components = spec.get("components")
    if not isinstance(components, dict):
        fail("spec.components must be an object")
    present = set(components)
    missing = sorted(COMPONENT_KEYS - present)
    if missing:
        fail(f"substrate is missing components of W: {missing} "
             f"(W = (S_dur, S_act, Theta, T, C, Pi, E))")
    unknown = sorted(present - COMPONENT_KEYS)
    if unknown:
        fail(f"substrate declares unknown components (not in W): {unknown}")
    for name in sorted(COMPONENT_KEYS):
        check_component(name, components[name])

    # --- structural attributes: order cycle, Hopf tower, dual sector, M(Psi) ---
    for key in ("orderCycle", "hopfTower", "dualSector", "balanceObservable"):
        if key not in spec:
            fail(f"spec.{key} is required (the substrate must declare its {key})")

    oc = spec["orderCycle"]
    no_extra(oc, {"present", "liftOperator", "mechanismRef", "verdict"}, "spec.orderCycle")
    if not isinstance(oc.get("present"), bool):
        fail("spec.orderCycle.present must be a boolean")
    need_str(oc, "liftOperator", "spec.orderCycle")
    check_mechanism_ref(need_str(oc, "mechanismRef", "spec.orderCycle"), "spec.orderCycle")
    check_verdict(oc, "spec.orderCycle")

    ht = spec["hopfTower"]
    no_extra(ht, {"levels", "mechanismRef", "verdict"}, "spec.hopfTower")
    if ht.get("levels") != ["H0", "H1", "H2", "H3"]:
        fail("spec.hopfTower.levels must be exactly [H0, H1, H2, H3]")
    check_mechanism_ref(need_str(ht, "mechanismRef", "spec.hopfTower"), "spec.hopfTower")
    check_verdict(ht, "spec.hopfTower")

    ds = spec["dualSector"]
    no_extra(ds, {"manifest", "latent", "mechanismRef", "verdict"}, "spec.dualSector")
    if ds.get("manifest") != "V+":
        fail("spec.dualSector.manifest must be 'V+' (the manifest sector)")
    if ds.get("latent") != "V-":
        fail("spec.dualSector.latent must be 'V-' (the latent sector)")
    check_mechanism_ref(need_str(ds, "mechanismRef", "spec.dualSector"), "spec.dualSector")
    check_verdict(ds, "spec.dualSector")

    bo = spec["balanceObservable"]
    no_extra(bo, {"symbol", "mechanismRef", "verdict"}, "spec.balanceObservable")
    if bo.get("symbol") != "M(Psi)":
        fail("spec.balanceObservable.symbol must be 'M(Psi)'")
    check_mechanism_ref(need_str(bo, "mechanismRef", "spec.balanceObservable"), "spec.balanceObservable")
    check_verdict(bo, "spec.balanceObservable")

    if "monodromy" in spec:
        md = spec["monodromy"]
        no_extra(md, {"mechanismRef", "verdict"}, "spec.monodromy")
        check_mechanism_ref(need_str(md, "mechanismRef", "spec.monodromy"), "spec.monodromy")
        check_verdict(md, "spec.monodromy")


def validate_schema(schema: Any) -> None:
    """Exercise the published schema and assert it stays in lockstep with this
    validator's invariants, so the two cannot silently drift."""
    if not isinstance(schema, dict):
        fail("schema must be an object")
    if schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
        fail("schema must use JSON Schema draft 2020-12")
    if schema.get("additionalProperties") is not False:
        fail("schema root must be strict (additionalProperties:false)")
    props = schema.get("properties", {})
    if props.get("kind", {}).get("const") != "WorldModelSubstrate":
        fail("schema kind const mismatch")
    spec = props.get("spec", {})
    comp = spec.get("properties", {}).get("components", {})
    if comp.get("additionalProperties") is not False:
        fail("schema components must be strict (additionalProperties:false)")
    if set(comp.get("required", [])) != COMPONENT_KEYS:
        fail("schema components.required drifted from validator COMPONENT_KEYS")
    if set(comp.get("properties", {})) != COMPONENT_KEYS:
        fail("schema components.properties drifted from validator COMPONENT_KEYS")
    spec_required = set(spec.get("required", []))
    for key in ("components", "orderCycle", "hopfTower", "dualSector", "balanceObservable"):
        if key not in spec_required:
            fail(f"schema spec.required must include {key!r}")
    ds = spec.get("properties", {}).get("dualSector", {}).get("properties", {})
    if ds.get("manifest", {}).get("const") != "V+":
        fail("schema must pin dualSector.manifest const 'V+'")
    if ds.get("latent", {}).get("const") != "V-":
        fail("schema must pin dualSector.latent const 'V-'")


def main() -> int:
    try:
        _assert_binding_maps_consistent()  # binding maps in lockstep with registry
        validate_schema(load(SCHEMA))     # schema is exercised, not just parsed
        validate_substrate(load(EXAMPLE))  # canonical example must pass
        for path in INVALID:
            try:
                validate_substrate(load(path))
            except ValidationError:
                continue
            fail(f"expected {path.name} to be rejected, but it passed")
    except ValidationError as exc:
        print(f"ERR: {exc}", file=sys.stderr)
        return 2
    print("OK: WorldModelSubstrate validation passed "
          f"(schema in lockstep, 1 example verified, {len(INVALID)} invalid rejected)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
