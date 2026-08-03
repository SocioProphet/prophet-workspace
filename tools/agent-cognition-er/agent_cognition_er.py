#!/usr/bin/env python3
"""AgentCognitionER — the typed entity/relation contract for governed agent cognition (ER-1).

This is the DATA-MODEL companion to ADR-0002 (Governed Cognition as an Emergent Functor). ADR-0002
audits the estate's cognition *loop* (five layers, thirteen steps) against one reference architecture.
This module makes the reference **entity-relation** model of that cognition — "auditable & reproducible
by construction" — a typed, validatable contract, and binds every entity to the *already-existing*
estate mechanism that owns it (`mechanism_ref`). Consume-not-fork: no entity here invents a new store;
each one names the mechanism that already implements it.

The unifying claim (the ER's "by construction"):
  - every ACTION is `gated_by` a POLICY_CHECK and `recorded_as` an AUDIT_EVENT — this is AC-1/AC-2 of
    ADR-0002 expressed on the graph (no action without lawful promotion, no promotion without a receipt);
  - every PROVENANCE_RECORD `depends_on` a DATASET_VERSION and `includes` a MODEL_VERSION — a receipt is
    not replayable if it cannot name the data + model it was produced under (ModelCarryManifest);
  - every memory item carries a `topic_set` + `span` + `domain` — memory is scoped, never ambient.

An instance that violates any of these is REJECTED by `validate_er_instance()` (see tests/). That is
what "auditable by construction" means here: the illegal states are unrepresentable in a *valid*
instance, so an auditor reads structure, not prose.

Dependency-light (stdlib only), matching this repo's convention. The JSON Schema in `schemas/` is
*exercised* by `validate_schema()` so the published schema and these Python teeth cannot silently drift.
Run: `python3 tools/agent-cognition-er/validate_agent_cognition_er.py`
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable


# --------------------------------------------------------------------------------------------------
# Verdict vocabulary (same as ADR-0002 §4): HAVE (shipped+tested), PARTIAL (exists, not fully wired),
# GAP (not built). Each entity/relation carries its verdict + the owning estate mechanism.
# --------------------------------------------------------------------------------------------------
HAVE = "HAVE"
PARTIAL = "PARTIAL"
GAP = "GAP"
VERDICTS = {HAVE, PARTIAL, GAP}


@dataclass(frozen=True)
class Entity:
    """One ER entity, bound to the estate mechanism that already owns it."""
    name: str
    role: str
    mechanism: str            # human name of the owning mechanism
    mechanism_ref: str        # estate-relative path / schema / issue that implements it
    verdict: str
    key_fields: tuple[str, ...]          # fields an instance record of this entity MUST carry
    memory_scoped: bool = False          # True => instances MUST carry topic_set + span + domain

    def __post_init__(self) -> None:
        if self.verdict not in VERDICTS:
            raise ValueError(f"{self.name}: bad verdict {self.verdict!r}")


@dataclass(frozen=True)
class Relation:
    """One typed edge subject --predicate--> object, with cardinality + whether it is REQUIRED.

    `required_on` names the endpoint on which the edge is mandatory for a valid instance
    (e.g. ACTION-gated_by-POLICY_CHECK is required on every ACTION). `None` => optional edge.
    """
    subject: str
    predicate: str
    object: str
    cardinality: str          # "1", "0..1", "1..*", "0..*"
    verdict: str
    mechanism_ref: str
    required_on: str | None = None   # "subject" => every subject instance MUST have >=1 such edge

    def __post_init__(self) -> None:
        if self.verdict not in VERDICTS:
            raise ValueError(f"{self.subject}-{self.predicate}->{self.object}: bad verdict {self.verdict!r}")


# --------------------------------------------------------------------------------------------------
# THE ENTITIES (17) — each bound to its owning estate mechanism (consume-not-fork).
# Paths are estate-relative to ~/dev, verified 2026-08-03.
# --------------------------------------------------------------------------------------------------
ENTITIES: dict[str, Entity] = {e.name: e for e in [
    Entity("AGENT", "the cognizing principal (identity + authority)",
           "agent-registry TrustChainAgentManifestBinding + agent-authority-decision "
           "(AgentPassport proper lives in mcp-a2a-zero-trust / ProCybernetica-aec)",
           "agent-registry/schemas/trust-chain-agent-manifest-binding.v0.1.schema.json ; "
           "agent-registry/contracts/trustops/agent-authority-decision.v0.1.schema.json",
           HAVE, ("agent_id", "passport_ref")),
    Entity("DECISION_CYCLE", "one governed cognition loop instance (ADR-0002 13-step loop)",
           "ADR-0002 governed cognition functor",
           "prophet-workspace/docs/adr/ADR-0002-governed-cognition-functor.md",
           HAVE, ("cycle_id", "agent_id", "started_at")),
    Entity("OBSERVATION", "a sensed/retrieved fact entering a cycle (episodic memory)",
           "memory-mesh EpisodeBundle (episodic) + receipt-spine run package",
           "memory-mesh/schemas/episode-bundle.schema.json ; "
           "prophet-workspace/tools/proof-artifact-spine/ (RunPackage)",
           HAVE, ("observation_id", "cycle_id"), memory_scoped=True),
    Entity("GRAPH_ENTITY", "a node in the canonical knowledge graph (semantic memory)",
           "HellGraph GraphNode/NodeAtom (bitemporal via regis node)",
           "hellgraph/ts/src/types.ts (GraphNode) ; hellgraph/crates/hg_core/src/lib.rs (NodeAtom) ; "
           "regis-entity-graph/schemas/node.schema.json (bitemporal)",
           HAVE, ("entity_id",), memory_scoped=True),
    Entity("GRAPH_EDGE", "an edge between graph entities (governance-bearing / bitemporal)",
           "HellGraph GraphEdge/LinkAtom + cskg-edge (governance) + regis edge (bitemporal)",
           "hellgraph/ts/src/types.ts (GraphEdge) ; "
           "prophet-workspace/tools/cskg-edge/schemas/cskg-edge.schema.json ; "
           "regis-entity-graph/schemas/edge.schema.json",
           HAVE, ("edge_id", "node1", "node2", "relation")),
    Entity("FAIR_OBJECT", "a Findable/Accessible/Interoperable/Reusable data object at rest",
           "metadata-standards metadata-record (identity/integrity block) + metadata-intake",
           "metadata-standards/schemas/metadata-record.schema.json ; "
           "prophet-workspace/tools/metadata-intake/",
           HAVE, ("object_id", "content_hash")),
    Entity("FAIR_METADATA", "the FAIR metadata + lineage describing a graph entity / object",
           "metadata-standards metadata-record (provenance.parent_artifact_id = lineage edge)",
           "metadata-standards/schemas/metadata-record.schema.json",
           HAVE, ("metadata_id", "describes")),
    Entity("PROVENANCE_RECORD", "a hash-chained, replayable receipt for a publish (the audit spine)",
           "proof-artifact-spine (knowledge) / InferenceReceipt (inference)",
           "prophet-workspace/tools/proof-artifact-spine/proof_artifact.py",
           HAVE, ("record_id", "record_type", "ledger_prev_hash", "dataset_version", "model_version")),
    Entity("VECTOR_CHUNK", "an embedded, indexed chunk of a FAIR object (vector memory)",
           "memoryd QdrantMemoryIndex point (vector + payload/ScopeEnvelope); no first-class chunk schema",
           "prophet-platform/apps/memoryd/src/memoryd/qdrant_index.py ; "
           "prophet-platform/apps/memoryd/src/memoryd/models.py (MemoryHit, ScopeEnvelope)",
           PARTIAL, ("chunk_id", "object_id", "embedding_ref"), memory_scoped=True),
    Entity("ACTION", "a state-changing act an agent emits (write/publish/grant/ship)",
           "policy-fabric lanes + capability-membrane (the gated act)",
           "prophet-platform/tools/capability_membrane.py",
           HAVE, ("action_id", "agent_id", "kind")),
    Entity("POLICY_CHECK", "the admission decision that gates an action (outcome, reason_code)",
           "policy-fabric decision engine (purpose #100, region #101, wallguard). "
           "The shared-state/live-activation decision (#102) is NOT on main → GAP",
           "policy-fabric/contracts/governed-action-policy-decision.v0.schema.json ; "
           "policy-fabric/contracts/purpose_admissibility_gate_decision_v1.schema.json",
           HAVE, ("check_id", "action_id", "outcome", "reason_code")),
    Entity("AUDIT_EVENT", "the append-only, tamper-evident log entry an action is recorded as",
           "receipt spine / agentplane evidence journal",
           "agentplane/evidence/append_event_stub.py ; proof-artifact-spine ledger",
           HAVE, ("event_id", "action_id", "event_hash")),
    Entity("BELIEF_STATE", "the agent's current working state / world-model snapshot (working memory)",
           "memory-mesh WorkingMemoryState (per-session, expires_at) + node_descriptor memory block",
           "memory-mesh/schemas/working-memory-state.schema.json ; "
           "ProCybernetica/schemas/node_descriptor.schema.json (memory)",
           PARTIAL, ("belief_id", "agent_id"), memory_scoped=True),
    Entity("PLAN", "the selected plan of steps for a cycle (procedural memory)",
           "memory-mesh ProceduralMemoryBundle + run-package plan (ADR-0001 AC-3)",
           "memory-mesh/schemas/procedural-memory-bundle.schema.json ; "
           "prophet-workspace/tools/proof-artifact-spine/ (RunPackage.plan)",
           HAVE, ("plan_id", "cycle_id", "steps"), memory_scoped=True),
    Entity("EVIDENCE_BUNDLE", "the bundle of evidence a cycle references (receipts + citations)",
           "EvidenceBundle IS a ProofArtifact (image-promotion-gate)",
           "prophet-workspace/tools/image-promotion-gate/ ; proof-artifact-spine",
           HAVE, ("bundle_id", "cycle_id", "provenance_refs")),
    Entity("DATASET_VERSION", "the pinned dataset version a provenance record depends on",
           "sourceos-model-carry provenance (sha256RequiredBeforeEligibility) + embedding-carry-ref; "
           "no first-class versioned DATASET entity yet → GAP",
           "sourceos-model-carry/contracts/model-carry-manifest.schema.json (provenance) ; "
           "sourceos-model-carry/examples/embedding-carry-ref.json",
           PARTIAL, ("dataset_version_id", "content_hash")),
    Entity("MODEL_VERSION", "the pinned model version a provenance record was produced with",
           "sourceos-model-carry ModelCarryManifest entries (modelRef + contentSha256 + version)",
           "sourceos-model-carry/contracts/model-carry-manifest.schema.json ; "
           "sourceos-model-carry/contracts/model-carry-pack.schema.json (model identity)",
           HAVE, ("model_version_id", "content_hash")),
]}


# --------------------------------------------------------------------------------------------------
# THE RELATIONS — the reference ER edges, each typed + carded + verdicted + bound.
# --------------------------------------------------------------------------------------------------
RELATIONS: list[Relation] = [
    Relation("AGENT", "runs", "DECISION_CYCLE", "1..*", HAVE,
             "prophet-workspace/docs/adr/ADR-0002-governed-cognition-functor.md"),
    Relation("AGENT", "maintains", "BELIEF_STATE", "1", PARTIAL,
             "ProCybernetica/schemas/node_descriptor.schema.json"),
    Relation("AGENT", "selects", "PLAN", "0..*", HAVE,
             "prophet-workspace/tools/proof-artifact-spine/proof_artifact.py"),
    Relation("AGENT", "emits", "ACTION", "0..*", HAVE,
             "prophet-platform/tools/capability_membrane.py"),
    Relation("AGENT", "evaluates", "POLICY_CHECK", "0..*", HAVE,
             "policy-fabric/contracts/"),
    Relation("DECISION_CYCLE", "consumes", "OBSERVATION", "0..*", HAVE,
             "prophet-workspace/tools/proof-artifact-spine/ (RunPackage)"),
    Relation("DECISION_CYCLE", "references", "EVIDENCE_BUNDLE", "0..*", HAVE,
             "prophet-workspace/tools/image-promotion-gate/"),
    Relation("OBSERVATION", "about", "GRAPH_ENTITY", "0..*", HAVE,
             "prophet-workspace/tools/cypher-atomspace-gateway/"),
    Relation("OBSERVATION", "stored_as", "FAIR_OBJECT", "0..1", HAVE,
             "prophet-workspace/tools/metadata-intake/"),
    Relation("GRAPH_ENTITY", "linked_by", "GRAPH_EDGE", "0..*", HAVE,
             "prophet-workspace/tools/cskg-edge/schemas/cskg-edge.schema.json"),
    Relation("GRAPH_ENTITY", "described_by", "FAIR_METADATA", "1", PARTIAL,
             "metadata-standards/"),
    Relation("FAIR_OBJECT", "generated_by", "PROVENANCE_RECORD", "1", HAVE,
             "prophet-workspace/tools/proof-artifact-spine/proof_artifact.py"),
    Relation("FAIR_OBJECT", "indexed_as", "VECTOR_CHUNK", "0..*", PARTIAL,
             "embeddinglab/"),
    # --- THE TEETH: these three edges are REQUIRED on their subject (auditable-by-construction) ---
    Relation("ACTION", "gated_by", "POLICY_CHECK", "1..*", HAVE,
             "policy-fabric/contracts/ ; prophet-platform/tools/capability_membrane.py",
             required_on="subject"),
    Relation("ACTION", "recorded_as", "AUDIT_EVENT", "1..*", HAVE,
             "agentplane/evidence/append_event_stub.py",
             required_on="subject"),
    Relation("ACTION", "causes_updates", "GRAPH_ENTITY", "0..*", HAVE,
             "prophet-workspace/tools/cypher-atomspace-gateway/"),
    Relation("PROVENANCE_RECORD", "depends_on", "DATASET_VERSION", "1..*", PARTIAL,
             "sourceos-model-carry/contracts/model-carry-manifest.schema.json (provenance; no first-class dataset version)",
             required_on="subject"),
    Relation("PROVENANCE_RECORD", "includes", "MODEL_VERSION", "1..*", HAVE,
             "sourceos-model-carry/contracts/model-carry-manifest.schema.json (entries[].modelRef+contentSha256)",
             required_on="subject"),
]


# Relations that MUST exist on every instance of their subject entity (the teeth).
def required_edges() -> list[Relation]:
    return [r for r in RELATIONS if r.required_on == "subject"]


# Entities whose instances are memory items and MUST carry topic_set + span + domain.
MEMORY_SCOPED = tuple(e.name for e in ENTITIES.values() if e.memory_scoped)

# The mandatory memory-scoping fields (see memory_binding.py for the full binding).
MEMORY_SCOPE_FIELDS = ("topic_set", "span", "domain")


class ERError(Exception):
    pass


def _fail(msg: str) -> None:
    raise ERError(msg)


# --------------------------------------------------------------------------------------------------
# THE VALIDATOR — teeth over an ER instance.
# An instance is: {"entities": {ENTITY_NAME: [record, ...]}, "edges": [[subj_id, predicate, obj_id], ...]}.
# --------------------------------------------------------------------------------------------------
def validate_er_instance(instance: dict) -> None:
    """Reject any instance that is not auditable-by-construction. Raises ERError on the first violation.

    Teeth:
      T1  every entity record carries its declared key_fields.
      T2  every memory-scoped record carries topic_set + span + domain (non-empty).
      T3  every ACTION has >=1 gated_by POLICY_CHECK edge AND >=1 recorded_as AUDIT_EVENT edge.
      T4  every PROVENANCE_RECORD has >=1 depends_on DATASET_VERSION AND >=1 includes MODEL_VERSION edge
          (and its dataset_version / model_version key fields are populated).
      T5  every edge references known entity ids and matches a declared RELATION (subject/predicate/object).
      T6  every POLICY_CHECK referenced by an ACTION carries an outcome + reason_code (typed decision).
    """
    if not isinstance(instance, dict) or "entities" not in instance or "edges" not in instance:
        _fail("instance must be an object with 'entities' and 'edges'")

    ent_blocks = instance["entities"]
    edges = instance["edges"]

    # id -> entity_type index, plus id -> record
    id_type: dict[str, str] = {}
    id_record: dict[str, dict] = {}

    for etype, records in ent_blocks.items():
        if etype not in ENTITIES:
            _fail(f"unknown entity type: {etype}")
        spec = ENTITIES[etype]
        for rec in records:
            # T1 key fields
            rec_id = rec.get(spec.key_fields[0])
            if not rec_id:
                _fail(f"{etype}: record missing primary key {spec.key_fields[0]!r}")
            for kf in spec.key_fields:
                if kf not in rec or rec[kf] in (None, "", [], {}):
                    _fail(f"{etype}[{rec_id}]: missing required key field {kf!r}")
            # T2 memory scoping
            if spec.memory_scoped:
                for mf in MEMORY_SCOPE_FIELDS:
                    val = rec.get(mf)
                    if val in (None, "", [], {}):
                        _fail(f"{etype}[{rec_id}]: memory item missing {mf!r} "
                              f"(memory must be scoped: topic_set + span + domain)")
            id_type[str(rec_id)] = etype
            id_record[str(rec_id)] = rec

    # index edges by subject-id + predicate
    valid_rel = {(r.subject, r.predicate, r.object) for r in RELATIONS}
    out_edges: dict[tuple[str, str], list[str]] = {}
    for edge in edges:
        if not (isinstance(edge, (list, tuple)) and len(edge) == 3):
            _fail(f"edge must be [subject_id, predicate, object_id]: {edge!r}")
        sid, pred, oid = str(edge[0]), edge[1], str(edge[2])
        # T5 referential + typed
        if sid not in id_type:
            _fail(f"edge subject id not found: {sid}")
        if oid not in id_type:
            _fail(f"edge object id not found: {oid}")
        rel_key = (id_type[sid], pred, id_type[oid])
        if rel_key not in valid_rel:
            _fail(f"edge is not a declared relation: {id_type[sid]} -{pred}-> {id_type[oid]}")
        out_edges.setdefault((sid, pred), []).append(oid)

    # T3 + T4 required edges on subjects
    for req in required_edges():
        for sid, etype in id_type.items():
            if etype != req.subject:
                continue
            targets = out_edges.get((sid, req.predicate), [])
            if not targets:
                _fail(f"{req.subject}[{sid}]: REJECTED — missing required edge "
                      f"'{req.predicate} {req.object}' (auditable-by-construction)")

    # T6 typed policy decision on every gating POLICY_CHECK
    for sid, etype in id_type.items():
        if etype != "ACTION":
            continue
        for pc_id in out_edges.get((sid, "gated_by"), []):
            pc = id_record[pc_id]
            if not pc.get("outcome") or not pc.get("reason_code"):
                _fail(f"POLICY_CHECK[{pc_id}] gating ACTION[{sid}]: missing outcome/reason_code "
                      f"(untyped decision)")


# --------------------------------------------------------------------------------------------------
# Introspection helpers (used by validate_agent_cognition_er.py + tests + the conformance matrix).
# --------------------------------------------------------------------------------------------------
def tally() -> dict[str, dict[str, int]]:
    """HAVE/PARTIAL/GAP counts for entities and relations."""
    def count(items: list) -> dict[str, int]:
        out = {HAVE: 0, PARTIAL: 0, GAP: 0}
        for it in items:
            out[it.verdict] += 1
        return out
    return {"entities": count(list(ENTITIES.values())), "relations": count(RELATIONS)}


if __name__ == "__main__":
    t = tally()
    print("AgentCognitionER — entities:", len(ENTITIES), "relations:", len(RELATIONS))
    print("  entity verdicts:  ", t["entities"])
    print("  relation verdicts:", t["relations"])
    print("  memory-scoped:    ", MEMORY_SCOPED)
