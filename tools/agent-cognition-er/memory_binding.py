#!/usr/bin/env python3
"""Memory-type ↔ AgentCognitionER binding (ER-1, second half).

Two memory models must reconcile onto ONE ER:

  (a) the estate's FSMS memory types (memory-mesh#47): working / episodic / semantic + procedural,
      with the short-term/long-term roles played by working (per-session, `expires_at`) and
      semantic-release (durable corpus), plus a ForgettingPolicy + PromotionRule that move items
      between tiers; and
  (b) the Claude memory pattern under evaluation: Memory.md (always-loaded index) · Topic Files
      (on-demand) · Transcripts (grep-only), with an auto-dream cycle
      Fork(isolation) → Distill/Merge → Conflict-Resolution → Prune(entropy) → Index-Sync.

This module maps BOTH onto the ER's memory-bearing nodes, and adds the scoping the estate today
expresses only piecemeal: **every memory item carries a topic_set + a span + a domain** (see
GAP-ER-2). A memory item without all three is REJECTED by the core validator (memory-scoped entities).

Consume-not-fork: the ER node column names the store that already holds the memory; the memory-mesh
schema column names the FSMS record; nothing new is invented.
"""
from __future__ import annotations

from dataclasses import dataclass

from agent_cognition_er import ENTITIES, MEMORY_SCOPE_FIELDS


@dataclass(frozen=True)
class MemoryBinding:
    memory_type: str
    er_nodes: tuple[str, ...]        # ER entity(ies) the memory type lands on
    memory_mesh_schema: str          # the FSMS record (memory-mesh#47) that realizes it
    claude_pattern: str              # the Claude memory-pattern analogue
    promotes_to: str | None          # PromotionRule destination (None => terminal / durable)
    forgetting: str                  # ForgettingPolicy disposition


# --------------------------------------------------------------------------------------------------
# THE BINDING TABLE — memory type → ER node(s) + FSMS schema + Claude pattern + promotion/forgetting.
# --------------------------------------------------------------------------------------------------
MEMORY_BINDINGS: list[MemoryBinding] = [
    MemoryBinding(
        "episodic", ("OBSERVATION", "AUDIT_EVENT"),
        "memory-mesh/schemas/episode-bundle.schema.json (EpisodeBundle)",
        "Transcripts (grep-only, append-only run log)",
        promotes_to="semantic", forgetting="ttl-based (retention_ttl, e.g. P30D)"),
    MemoryBinding(
        "short-term", ("OBSERVATION",),
        "memory-mesh/schemas/working-memory-state.schema.json (WorkingMemoryState.expires_at)",
        "current context window (in-cycle buffer)",
        promotes_to="working", forgetting="expires_at (per-session TTL)"),
    MemoryBinding(
        "working", ("BELIEF_STATE",),
        "memory-mesh/schemas/working-memory-state.schema.json (WorkingMemoryState)",
        "active scratchpad / plan_state",
        promotes_to="long-term", forgetting="expires_at + retention_class"),
    MemoryBinding(
        "semantic", ("GRAPH_ENTITY", "FAIR_METADATA"),
        "memory-mesh/schemas/semantic-memory-release.schema.json (cskg_edge_set_ref, topic_artifact_refs)",
        "Topic Files (on-demand, per-topic knowledge)",
        promotes_to=None, forgetting="explicit-delete-only (durable; retirement-not-destruction)"),
    MemoryBinding(
        "long-term", ("FAIR_OBJECT", "PROVENANCE_RECORD"),
        "memory-mesh/schemas/semantic-memory-release.schema.json (corpus_release_ref; PublishedCanonical)",
        "Memory.md (always-loaded index over durable corpus)",
        promotes_to=None, forgetting="explicit-delete-only (canonical; legal-hold override)"),
    MemoryBinding(
        "procedural", ("PLAN",),
        "memory-mesh/schemas/procedural-memory-bundle.schema.json (ProceduralMemoryBundle)",
        "skills / playbooks (recommendation_playbook_refs)",
        promotes_to=None, forgetting="active_flag toggle (rollback_plan, not delete)"),
]

MEMORY_BINDINGS_BY_TYPE = {b.memory_type: b for b in MEMORY_BINDINGS}


# --------------------------------------------------------------------------------------------------
# AUTO-DREAM ↔ estate promotion/forgetting phases.
# The Claude auto-dream cycle is not a new mechanism — each phase is an estate mechanism that
# already exists. Index-Sync is the Memory.md-style always-loaded index (openclaw MEMORY.md projection).
# --------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class DreamPhase:
    phase: str
    estate_mechanism: str
    er_effect: str


AUTO_DREAM_PHASES: list[DreamPhase] = [
    DreamPhase("Fork(isolation)",
               "isolated worktree / a DECISION_CYCLE run in isolation (no shared-state write)",
               "spawns a consolidation DECISION_CYCLE; reads memory, proposes writes (soft lane)"),
    DreamPhase("Distill / Merge",
               "memory-mesh PromotionRule.summarization_strategy (source→destination memory_class)",
               "episodic OBSERVATION → semantic GRAPH_ENTITY/FAIR_METADATA (promotion)"),
    DreamPhase("Conflict-Resolution",
               "PromotionRule.contradiction_policy + temporal-retrieval-filter (most-recent-fact wins)",
               "supersede stale GRAPH_ENTITY/edge; POLICY_CHECK gates the promotion write"),
    DreamPhase("Prune (entropy control)",
               "memory-mesh ForgettingPolicy (decay_strategy / compaction / purge_conditions)",
               "demote/retire memory items (retirement-not-destruction); emits AUDIT_EVENT"),
    DreamPhase("Index-Sync",
               "openclaw MEMORY.md projection (adapters/openclaw-memory-mesh) — the always-loaded index",
               "regenerate the Memory.md-style index over long-term/semantic nodes"),
]


class MemoryBindingError(Exception):
    pass


def validate_memory_binding() -> None:
    """Drift guard: every memory type must land on real ER memory-scoped nodes, and the auto-dream
    promotion targets must be known memory types. Keeps this binding honest against the core model."""
    memory_scoped = {e.name for e in ENTITIES.values() if e.memory_scoped}
    # semantic/long-term also land on FAIR_METADATA / FAIR_OBJECT / PROVENANCE_RECORD / AUDIT_EVENT,
    # which are not memory-scoped (they are durable/audit records, not scoped memory items). The
    # SCOPED landing node of every type must exist and at least one binding must hit a scoped node.
    for b in MEMORY_BINDINGS:
        for node in b.er_nodes:
            if node not in ENTITIES:
                raise MemoryBindingError(f"{b.memory_type}: unknown ER node {node!r}")
        if b.promotes_to is not None and b.promotes_to not in MEMORY_BINDINGS_BY_TYPE:
            raise MemoryBindingError(f"{b.memory_type}: promotes_to unknown type {b.promotes_to!r}")
    # the volatile tiers (episodic/short-term/working) must map to a memory-scoped node
    for t in ("episodic", "short-term", "working"):
        nodes = set(MEMORY_BINDINGS_BY_TYPE[t].er_nodes)
        if not (nodes & memory_scoped):
            raise MemoryBindingError(f"{t}: must land on a memory-scoped ER node (topic_set/span/domain)")


def make_memory_item(er_node: str, *, topic_set: list[str], span: dict, domain: str, **fields) -> dict:
    """Build a valid ER memory item — the (topic_set, span, domain) envelope is mandatory.

    span is an interval object, e.g. {"valid_from": "...", "valid_to": null} (maps to
    memory-mesh valid_from/valid_to / working-memory expires_at). Raises if the envelope is incomplete.
    """
    if er_node not in ENTITIES or not ENTITIES[er_node].memory_scoped:
        raise MemoryBindingError(f"{er_node} is not a memory-scoped ER node")
    if not topic_set or not isinstance(topic_set, list):
        raise MemoryBindingError("topic_set must be a non-empty list")
    if not span or not isinstance(span, dict):
        raise MemoryBindingError("span must be a non-empty interval object")
    if not domain or not isinstance(domain, str):
        raise MemoryBindingError("domain must be a non-empty string")
    item = dict(fields)
    item["topic_set"] = topic_set
    item["span"] = span
    item["domain"] = domain
    return item


if __name__ == "__main__":
    validate_memory_binding()
    print("memory-type ↔ ER binding — OK")
    print(f"  scoping envelope required on every memory item: {MEMORY_SCOPE_FIELDS}")
    print(f"  {'memory type':<12} {'ER node(s)':<34} claude pattern")
    for b in MEMORY_BINDINGS:
        print(f"  {b.memory_type:<12} {'+'.join(b.er_nodes):<34} {b.claude_pattern}")
    print("  auto-dream phases:")
    for d in AUTO_DREAM_PHASES:
        print(f"    {d.phase:<20} -> {d.estate_mechanism}")
