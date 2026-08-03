#!/usr/bin/env python3
"""Validate CompositionGraph records (WO-K, Open Agent Continuum / ADR-0001).

A CompositionGraph is the ORCHESTRATION artifact: how many governed agents/organs compose into ONE
bounded, receipted workflow DAG. Where GenesisSeed (WO-J) is the formation charter of a SINGLE twin, a
CompositionGraph is the plural — a Triune/AUM-style DAG whose nodes are seeded agent-roles with a
capability envelope, a time-box and a danger class, whose edges are data/control dependencies, and whose
gates reference the policy/eval/quorum machinery the estate already owns.

Consume-not-fork bindings (the graph does not re-implement anything the continuum already built):
  - each node's seed_ref binds a GenesisSeed (schemas/genesis-seed.schema.json), which instantiates a
    WorkspaceMountTable (the f* capability surface); the node does not re-declare the seed's profiles;
  - gates reference Sentinel policy + SEC-2 witness-quorum (tools/proof-artifact-spine/witness_quorum.py)
    — the graph is not a new policy engine;
  - the whole run is a hash-chained ProofArtifact on the proof-artifact-spine (f_!, AC-1);
  - tool_exec nodes route through agent-term's disposable-VM controller (WO-F);
  - the epistemic ceiling is computed by tools/workspace-controller (WO-C).

Invariants (fail-closed), teeth both ways:
  - **Shape.** additionalProperties:false everywhere; all required fields present; enumerated vocab.
  - **Referential integrity.** node_ids unique; every edge/gate reference resolves to a declared node;
    an edge does not self-loop.
  - **Governed DAG (loops-vs-DAGs).** Graph-level control flow is ACYCLIC; the only legal cycle is a
    node declared loop:true carrying budget.max_iterations (DAG = acyclic identity; loop = correction,
    bounded + convergent + fail-closed).
  - **Bounded iteration.** A loop node MUST carry budget.max_iterations; a non-loop node MUST NOT carry
    a budget — no accidental unbounded correction.
  - **Every node time-boxed.** ttl_seconds is a positive integer on every node — no unbounded residency.
  - **Fail-closed actuation.** Any node with danger_class 'high' or a mutating/host provider
    (provider:kubernetes | provider:host | *host_update*) MUST be covered by a quorum gate.
  - **Mandatory kill-switch.** revocation.kill_switch MUST be true — instant blast-radius containment.
  - **Receipted composition (AC-1).** receipt_profile requires per_node + run receipts and append-only
    provenance — a composition run without a receipt is a bug.
  - **Bounded federation.** federation_profile is a closed enum.

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
SCHEMA = ROOT / "schemas/composition-graph.schema.json"
EXAMPLE = ROOT / "examples/composition-graph.example.json"
INVALID = [
    ROOT / "examples/composition-graph.cyclic.invalid.json",
    ROOT / "examples/composition-graph.dangling-edge.invalid.json",
    ROOT / "examples/composition-graph.unbounded-node.invalid.json",
    ROOT / "examples/composition-graph.unbounded-loop.invalid.json",
    ROOT / "examples/composition-graph.unquorum-host-mutation.invalid.json",
    ROOT / "examples/composition-graph.no-kill-switch.invalid.json",
]

TOP_KEYS = {"graph_id", "federation_profile", "revocation", "receipt_profile", "nodes", "edges", "gates"}
REVOCATION_KEYS = {"scope", "kill_switch"}
REVOCATION_SCOPES = {"label", "grant", "both"}
RECEIPT_KEYS = {"per_node", "run", "provenance"}
NODE_KEYS = {"node_id", "seed_ref", "archetype", "organs", "danger_class", "ttl_seconds",
             "loop", "budget", "provider_profile", "approval"}
NODE_REQUIRED = {"node_id", "seed_ref", "organs", "danger_class", "ttl_seconds"}
BUDGET_KEYS = {"max_iterations"}
EDGE_KEYS = {"from", "to", "kind"}
EDGE_KINDS = {"data", "control"}
GATE_KEYS = {"gate_id", "kind", "applies_to"}
GATE_KINDS = {"policy", "eval", "quorum"}
DANGER_CLASSES = {"low", "medium", "high"}
FEDERATION_MODES = {"none", "same_domain_only", "cross_domain_reviewed"}
APPROVAL_STATES = {"required", "optional", "not_required"}

# Providers whose use implies host/world mutation → force quorum-gate coverage (same rule as GenesisSeed).
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


def need_str(obj: dict[str, Any], key: str, ctx: str) -> str:
    value = obj.get(key)
    if not isinstance(value, str) or not value:
        fail(f"{ctx}.{key}: expected non-empty string")
    return value  # type: ignore[return-value]


def need_str_list(obj: dict[str, Any], key: str, ctx: str, *, min_items: int) -> list[str]:
    value = obj.get(key)
    if not isinstance(value, list) or len(value) < min_items:
        fail(f"{ctx}.{key}: expected array with at least {min_items} item(s)")
    if any(not isinstance(v, str) or not v for v in value):
        fail(f"{ctx}.{key}: every item must be a non-empty string")
    if len(set(value)) != len(value):
        fail(f"{ctx}.{key}: items must be unique (the profile is a set)")
    return value  # type: ignore[return-value]


def no_extra(obj: dict[str, Any], allowed: set[str], ctx: str) -> None:
    extra = sorted(set(obj) - allowed)
    if extra:
        fail(f"unexpected fields in {ctx}: {extra}")


def _mutates_host(provider_profile: list[str]) -> bool:
    return any(p in _MUTATING_PROVIDERS or "host_update" in p for p in provider_profile)


def _acyclic(node_ids: list[str], edges: list[dict[str, Any]]) -> bool:
    """Kahn's algorithm over control+data edges — the graph minus its declared loop nodes must be a DAG."""
    indeg = {n: 0 for n in node_ids}
    adj: dict[str, list[str]] = {n: [] for n in node_ids}
    for e in edges:
        adj[e["from"]].append(e["to"])
        indeg[e["to"]] += 1
    queue = [n for n in node_ids if indeg[n] == 0]
    seen = 0
    while queue:
        n = queue.pop()
        seen += 1
        for m in adj[n]:
            indeg[m] -= 1
            if indeg[m] == 0:
                queue.append(m)
    return seen == len(node_ids)


def validate_composition_graph(record: Any) -> None:
    """Enforce the WO-K invariants on one CompositionGraph. Raises ValidationError."""
    if not isinstance(record, dict):
        fail("record must be an object")
    no_extra(record, TOP_KEYS, "record")
    for k in TOP_KEYS:
        if k not in record:
            fail(f"record: missing required field {k!r}")

    need_str(record, "graph_id", "record")

    if record.get("federation_profile") not in FEDERATION_MODES:
        fail(f"federation_profile must be one of {sorted(FEDERATION_MODES)}")

    # revocation — mandatory kill-switch.
    revocation = record.get("revocation")
    if not isinstance(revocation, dict):
        fail("revocation: expected object")
    no_extra(revocation, REVOCATION_KEYS, "revocation")
    if revocation.get("scope") not in REVOCATION_SCOPES:
        fail(f"revocation.scope must be one of {sorted(REVOCATION_SCOPES)}")
    if revocation.get("kill_switch") is not True:
        fail("revocation.kill_switch must be true — a composition without an instant mass-terminate "
             "path has no blast-radius containment")

    # receipt_profile — receipted composition (AC-1).
    receipt = record.get("receipt_profile")
    if not isinstance(receipt, dict):
        fail("receipt_profile: expected object")
    no_extra(receipt, RECEIPT_KEYS, "receipt_profile")
    if receipt.get("per_node") is not True:
        fail("receipt_profile.per_node must be true — every publishing node is receipted (AC-1)")
    if receipt.get("run") is not True:
        fail("receipt_profile.run must be true — the run emits a run-level ProofArtifact (AC-1)")
    if receipt.get("provenance") != "append_only":
        fail("receipt_profile.provenance must be 'append_only' — provenance is never rewritten")

    # nodes.
    nodes = record.get("nodes")
    if not isinstance(nodes, list) or not nodes:
        fail("nodes: expected non-empty array")
    node_ids: list[str] = []
    loop_ids: set[str] = set()
    high_or_host: set[str] = set()
    for i, node in enumerate(nodes):
        ctx = f"nodes[{i}]"
        if not isinstance(node, dict):
            fail(f"{ctx}: expected object")
        no_extra(node, NODE_KEYS, ctx)
        for k in NODE_REQUIRED:
            if k not in node:
                fail(f"{ctx}: missing required field {k!r}")
        nid = need_str(node, "node_id", ctx)
        need_str(node, "seed_ref", ctx)
        need_str_list(node, "organs", ctx, min_items=1)
        node_ids.append(nid)

        if node.get("danger_class") not in DANGER_CLASSES:
            fail(f"{ctx}.danger_class must be one of {sorted(DANGER_CLASSES)}")

        ttl = node.get("ttl_seconds")
        if not isinstance(ttl, int) or isinstance(ttl, bool) or ttl < 1:
            fail(f"{ctx}.ttl_seconds must be a positive integer — every node is time-boxed")

        provider_profile = need_str_list(node, "provider_profile", ctx, min_items=0) \
            if "provider_profile" in node else []

        approval = node.get("approval", {})
        if not isinstance(approval, dict):
            fail(f"{ctx}.approval: expected object")
        for action, state in approval.items():
            if state not in APPROVAL_STATES:
                fail(f"{ctx}.approval.{action} must be one of {sorted(APPROVAL_STATES)}")

        # BOUNDED ITERATION: loop node <=> budget.max_iterations.
        is_loop = node.get("loop", False)
        if not isinstance(is_loop, bool):
            fail(f"{ctx}.loop: expected boolean")
        has_budget = "budget" in node
        if is_loop and not has_budget:
            fail(f"{ctx}: loop node must carry budget.max_iterations (bounded iteration)")
        if has_budget and not is_loop:
            fail(f"{ctx}: budget is only valid on a loop node (loop:true)")
        if has_budget:
            budget = node["budget"]
            if not isinstance(budget, dict):
                fail(f"{ctx}.budget: expected object")
            no_extra(budget, BUDGET_KEYS, f"{ctx}.budget")
            mi = budget.get("max_iterations")
            if not isinstance(mi, int) or isinstance(mi, bool) or mi < 1:
                fail(f"{ctx}.budget.max_iterations must be a positive integer")
        if is_loop:
            loop_ids.add(nid)

        if node.get("danger_class") == "high" or _mutates_host(provider_profile):
            high_or_host.add(nid)

    if len(set(node_ids)) != len(node_ids):
        fail("nodes: node_id values must be unique")
    id_set = set(node_ids)

    # edges — referential integrity + no self-loop.
    edges = record.get("edges")
    if not isinstance(edges, list):
        fail("edges: expected array")
    for i, edge in enumerate(edges):
        ctx = f"edges[{i}]"
        if not isinstance(edge, dict):
            fail(f"{ctx}: expected object")
        no_extra(edge, EDGE_KEYS, ctx)
        src = need_str(edge, "from", ctx)
        dst = need_str(edge, "to", ctx)
        if edge.get("kind") not in EDGE_KINDS:
            fail(f"{ctx}.kind must be one of {sorted(EDGE_KINDS)}")
        if src not in id_set:
            fail(f"{ctx}.from references unknown node {src!r}")
        if dst not in id_set:
            fail(f"{ctx}.to references unknown node {dst!r}")
        if src == dst:
            fail(f"{ctx}: self-loop {src!r} — a bounded loop is a loop node, not a self-edge")

    # GOVERNED DAG: graph-level control flow must be acyclic (loops live inside loop nodes).
    if not _acyclic(node_ids, edges):
        fail("edges form a cycle — graph-level control flow must be acyclic; a bounded correction "
             f"loop must be a node with loop:true + budget.max_iterations (declared loop nodes: "
             f"{sorted(loop_ids) or 'none'})")

    # gates — referential integrity + fail-closed actuation coverage.
    gates = record.get("gates")
    if not isinstance(gates, list) or not gates:
        fail("gates: expected non-empty array")
    quorum_covered: set[str] = set()
    for i, gate in enumerate(gates):
        ctx = f"gates[{i}]"
        if not isinstance(gate, dict):
            fail(f"{ctx}: expected object")
        no_extra(gate, GATE_KEYS, ctx)
        need_str(gate, "gate_id", ctx)
        kind = gate.get("kind")
        if kind not in GATE_KINDS:
            fail(f"{ctx}.kind must be one of {sorted(GATE_KINDS)}")
        applies = need_str_list(gate, "applies_to", ctx, min_items=1)
        for nid in applies:
            if nid not in id_set:
                fail(f"{ctx}.applies_to references unknown node {nid!r}")
        if kind == "quorum":
            quorum_covered.update(applies)

    # FAIL-CLOSED ACTUATION: high-danger / host-mutating nodes must be under a quorum gate.
    uncovered = sorted(high_or_host - quorum_covered)
    if uncovered:
        fail("fail-closed actuation: high-danger or host-mutating node(s) not covered by any quorum "
             f"gate: {uncovered}")


def validate_schema(schema: Any) -> None:
    """Exercise the published schema and assert it stays in lockstep with this validator's invariants,
    so the two cannot silently drift (dependency-light, per repo convention)."""
    if not isinstance(schema, dict):
        fail("schema must be an object")
    if schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
        fail("schema must use JSON Schema draft 2020-12")
    if schema.get("additionalProperties") is not False:
        fail("schema root must be strict (additionalProperties:false)")
    if set(schema.get("required", [])) != TOP_KEYS:
        fail("schema required drifted from validator TOP_KEYS")
    props = schema.get("properties", {})

    if set(props.get("federation_profile", {}).get("enum", [])) != FEDERATION_MODES:
        fail("schema federation_profile.enum drifted from validator FEDERATION_MODES")

    rev = props.get("revocation", {})
    if rev.get("additionalProperties") is not False or set(rev.get("required", [])) != REVOCATION_KEYS:
        fail("schema revocation must be strict with required {scope, kill_switch}")
    if rev.get("properties", {}).get("kill_switch", {}).get("const") is not True:
        fail("schema must pin revocation.kill_switch to const true")

    rcp = props.get("receipt_profile", {})
    if rcp.get("additionalProperties") is not False or set(rcp.get("required", [])) != RECEIPT_KEYS:
        fail("schema receipt_profile must be strict with required {per_node, run, provenance}")
    rprops = rcp.get("properties", {})
    if rprops.get("per_node", {}).get("const") is not True:
        fail("schema must pin receipt_profile.per_node to const true")
    if rprops.get("run", {}).get("const") is not True:
        fail("schema must pin receipt_profile.run to const true")
    if rprops.get("provenance", {}).get("const") != "append_only":
        fail("schema must pin receipt_profile.provenance to const 'append_only'")

    node = props.get("nodes", {}).get("items", {}).get("$ref")
    if node != "#/$defs/node":
        fail("schema nodes.items must $ref #/$defs/node")
    node_def = schema.get("$defs", {}).get("node", {})
    if node_def.get("additionalProperties") is not False:
        fail("schema $defs.node must be strict")
    if set(node_def.get("required", [])) != NODE_REQUIRED:
        fail("schema $defs.node.required drifted from validator NODE_REQUIRED")
    if set(node_def.get("properties", {}).get("danger_class", {}).get("enum", [])) != DANGER_CLASSES:
        fail("schema $defs.node.danger_class.enum drifted from validator DANGER_CLASSES")
    if node_def.get("properties", {}).get("ttl_seconds", {}).get("minimum") != 1:
        fail("schema $defs.node.ttl_seconds must pin minimum 1 (time-box)")

    gate_def = schema.get("$defs", {}).get("gate", {})
    if set(gate_def.get("properties", {}).get("kind", {}).get("enum", [])) != GATE_KINDS:
        fail("schema $defs.gate.kind.enum drifted from validator GATE_KINDS")
    edge_def = schema.get("$defs", {}).get("edge", {})
    if set(edge_def.get("properties", {}).get("kind", {}).get("enum", [])) != EDGE_KINDS:
        fail("schema $defs.edge.kind.enum drifted from validator EDGE_KINDS")


def main() -> int:
    try:
        validate_schema(load(SCHEMA))               # schema is exercised, not just parsed
        validate_composition_graph(load(EXAMPLE))   # canonical example must pass
        for path in INVALID:
            try:
                validate_composition_graph(load(path))
            except ValidationError:
                continue
            fail(f"expected {path.name} to be rejected, but it passed")
    except ValidationError as exc:
        print(f"ERR: {exc}", file=sys.stderr)
        return 2
    print(f"OK: CompositionGraph validation passed (1 example, {len(INVALID)} invalid rejected)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
