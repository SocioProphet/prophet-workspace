# AgentCognitionER (ER-1) — conformance matrix

- **Owner:** @mdheller
- **Status:** active
- **Date:** 2026-08-03
- **Companion to:** [ADR-0002 — Governed Cognition as an Emergent Functor](../../docs/adr/ADR-0002-governed-cognition-functor.md)
- **Reference diagram (origin of the tokens):** `prophet-platform/apps/socioprophet-web/public/workbench/unified_cognitive_systems_map.html` (the estate's "unified cognitive systems map" — where `AGENT / DECISION_CYCLE / OBSERVATION / GRAPH_ENTITY / GRAPH_EDGE / FAIR_OBJECT / FAIR_METADATA / PROVENANCE_RECORD / VECTOR_CHUNK / ACTION / POLICY_CHECK / AUDIT_EVENT / DATASET_VERSION / MODEL_VERSION / INDEXED_AS` are drawn).
- **Cross-refs:** ADR-0002 · memory-mesh#47 (FSMS memory schemas) · ontogenesis#140 (agent-identity metaphor→mechanism) · prophet-workspace#76 (item 2, cognition-functor) / #108 · policy-fabric#102 (shared-state/live-activation).

Where ADR-0002 audits the cognition **loop** (5 layers, 13 steps), this audits the cognition **entity/relation
model** — the data spine that is "auditable & reproducible by construction". Verdicts: **HAVE** (shipped + tested/merged), **PARTIAL** (mechanism exists but not first-class / not fully wired / on a non-main branch), **GAP** (not built). Paths are estate-relative to `~/dev`, verified 2026-08-03.

Consume-not-fork: every entity below names the estate mechanism that already owns it (`mechanism_ref`). This
module invents no new store; it binds the reference ER onto what exists and makes the illegal states
unrepresentable in a *valid* instance (see `agent_cognition_er.py`).

## Entities (17) — 14 HAVE · 3 PARTIAL · 0 GAP

| Entity | Verdict | Owning mechanism | `mechanism_ref` |
|---|---|---|---|
| `AGENT` | HAVE | agent-registry TrustChainAgentManifestBinding + agent-authority-decision (AgentPassport proper lives in mcp-a2a-zero-trust / ProCybernetica-aec) | `agent-registry/schemas/trust-chain-agent-manifest-binding.v0.1.schema.json` |
| `DECISION_CYCLE` | HAVE | ADR-0002 governed cognition functor (13-step loop) | `prophet-workspace/docs/adr/ADR-0002-governed-cognition-functor.md` |
| `OBSERVATION` | HAVE | memory-mesh EpisodeBundle (episodic) + receipt-spine run package | `memory-mesh/schemas/episode-bundle.schema.json` |
| `GRAPH_ENTITY` | HAVE | HellGraph GraphNode/NodeAtom; bitemporal via regis node | `hellgraph/ts/src/types.ts` ; `regis-entity-graph/schemas/node.schema.json` |
| `GRAPH_EDGE` | HAVE | HellGraph GraphEdge/LinkAtom + cskg-edge (governance) + regis edge (bitemporal) | `hellgraph/ts/src/types.ts` ; `prophet-workspace/tools/cskg-edge/schemas/cskg-edge.schema.json` |
| `FAIR_OBJECT` | HAVE | metadata-standards metadata-record (identity/integrity) + metadata-intake | `metadata-standards/schemas/metadata-record.schema.json` |
| `FAIR_METADATA` | HAVE | metadata-standards metadata-record (`provenance.parent_artifact_id` = lineage edge) | `metadata-standards/schemas/metadata-record.schema.json` |
| `PROVENANCE_RECORD` | HAVE | proof-artifact-spine (knowledge) / InferenceReceipt (inference) | `prophet-workspace/tools/proof-artifact-spine/proof_artifact.py` |
| `VECTOR_CHUNK` | PARTIAL | memoryd QdrantMemoryIndex point (vector + payload/ScopeEnvelope); **no first-class chunk schema** → GAP-ER-1 | `prophet-platform/apps/memoryd/src/memoryd/qdrant_index.py` |
| `ACTION` | HAVE | policy-fabric lanes + capability-membrane (the gated act) | `prophet-platform/tools/capability_membrane.py` |
| `POLICY_CHECK` | HAVE | policy-fabric decision engine (purpose #100, region #101, wallguard). Shared-state/live-activation (#102) **not on main** → GAP-ER-4 | `policy-fabric/contracts/governed-action-policy-decision.v0.schema.json` |
| `AUDIT_EVENT` | HAVE | receipt spine / agentplane evidence journal | `agentplane/evidence/append_event_stub.py` |
| `BELIEF_STATE` | PARTIAL | memory-mesh WorkingMemoryState (per-session, `expires_at`) + node_descriptor memory block; not wired into the live agent loop | `memory-mesh/schemas/working-memory-state.schema.json` |
| `PLAN` | HAVE | memory-mesh ProceduralMemoryBundle + run-package plan (ADR-0001 AC-3) | `memory-mesh/schemas/procedural-memory-bundle.schema.json` |
| `EVIDENCE_BUNDLE` | HAVE | EvidenceBundle IS a ProofArtifact (image-promotion-gate) | `prophet-workspace/tools/image-promotion-gate/` |
| `DATASET_VERSION` | PARTIAL | sourceos-model-carry provenance (`sha256RequiredBeforeEligibility`) + embedding-carry-ref; **no first-class versioned DATASET entity** → GAP-ER-3 | `sourceos-model-carry/contracts/model-carry-manifest.schema.json` |
| `MODEL_VERSION` | HAVE | sourceos-model-carry ModelCarryManifest entries (`modelRef` + `contentSha256` + `version`) | `sourceos-model-carry/contracts/model-carry-manifest.schema.json` |

## Relations (18) — 14 HAVE · 4 PARTIAL · 0 GAP  ·  **(REQUIRED)** = the teeth

| Relation | Card. | Verdict | `mechanism_ref` |
|---|---|---|---|
| `AGENT` –runs→ `DECISION_CYCLE` | 1..* | HAVE | ADR-0002 |
| `AGENT` –maintains→ `BELIEF_STATE` | 1 | PARTIAL | `ProCybernetica/schemas/node_descriptor.schema.json` |
| `AGENT` –selects→ `PLAN` | 0..* | HAVE | proof-artifact-spine (RunPackage) |
| `AGENT` –emits→ `ACTION` | 0..* | HAVE | capability_membrane |
| `AGENT` –evaluates→ `POLICY_CHECK` | 0..* | HAVE | policy-fabric/contracts/ |
| `DECISION_CYCLE` –consumes→ `OBSERVATION` | 0..* | HAVE | proof-artifact-spine (RunPackage) |
| `DECISION_CYCLE` –references→ `EVIDENCE_BUNDLE` | 0..* | HAVE | image-promotion-gate |
| `OBSERVATION` –about→ `GRAPH_ENTITY` | 0..* | HAVE | cypher-atomspace-gateway |
| `OBSERVATION` –stored_as→ `FAIR_OBJECT` | 0..1 | HAVE | metadata-intake |
| `GRAPH_ENTITY` –linked_by→ `GRAPH_EDGE` | 0..* | HAVE | cskg-edge |
| `GRAPH_ENTITY` –described_by→ `FAIR_METADATA` | 1 | PARTIAL | metadata-standards (lineage not universally attached) |
| `FAIR_OBJECT` –generated_by→ `PROVENANCE_RECORD` | 1 | HAVE | proof-artifact-spine |
| `FAIR_OBJECT` –indexed_as→ `VECTOR_CHUNK` | 0..* | PARTIAL | memoryd (no chunk↔object contract) → GAP-ER-1 |
| **`ACTION` –gated_by→ `POLICY_CHECK`** | 1..* | HAVE | policy-fabric + capability_membrane |
| **`ACTION` –recorded_as→ `AUDIT_EVENT`** | 1..* | HAVE | agentplane evidence journal |
| `ACTION` –causes_updates→ `GRAPH_ENTITY` | 0..* | HAVE | cypher-atomspace-gateway |
| **`PROVENANCE_RECORD` –depends_on→ `DATASET_VERSION`** | 1..* | PARTIAL | sourceos-model-carry → GAP-ER-3 |
| **`PROVENANCE_RECORD` –includes→ `MODEL_VERSION`** | 1..* | HAVE | sourceos-model-carry (ModelCarryManifest) |

## Tally

- **Entities:** 17 → **14 HAVE · 3 PARTIAL · 0 GAP.**
- **Relations:** 18 → **14 HAVE · 4 PARTIAL · 0 GAP.**
- **Combined:** 35 rows → **28 HAVE · 7 PARTIAL · 0 GAP.**
- **Teeth (the 4 REQUIRED edges):** enforced by `validate_er_instance()` — 3 HAVE, 1 PARTIAL (`depends_on DATASET_VERSION`, GAP-ER-3). No hard GAP; every PARTIAL has a named owning mechanism and a filed issue.

## Memory-type ↔ ER + topic-set/span-by-domain binding

Reconciles the estate FSMS memory types (memory-mesh#47) with the Claude memory pattern, onto the ER's
memory-bearing nodes. **Every memory item carries `topic_set` + `span` + `domain`** — a memory item without
all three is REJECTED (memory-scoped entities: `OBSERVATION`, `GRAPH_ENTITY`, `VECTOR_CHUNK`, `BELIEF_STATE`,
`PLAN`). See `memory_binding.py`.

| Memory type | ER node(s) | memory-mesh (#47) schema | Claude pattern | promotes→ | forgetting |
|---|---|---|---|---|---|
| episodic | `OBSERVATION` + `AUDIT_EVENT` | `episode-bundle.schema.json` | Transcripts (grep-only, append log) | semantic | ttl-based (`retention_ttl`) |
| short-term | `OBSERVATION` | `working-memory-state.schema.json` (`expires_at`) | current context window | working | `expires_at` |
| working | `BELIEF_STATE` | `working-memory-state.schema.json` | active scratchpad / `plan_state` | long-term | `expires_at` + `retention_class` |
| semantic | `GRAPH_ENTITY` + `FAIR_METADATA` | `semantic-memory-release.schema.json` (`cskg_edge_set_ref`) | Topic Files (on-demand) | — (durable) | explicit-delete-only |
| long-term | `FAIR_OBJECT` + `PROVENANCE_RECORD` | `semantic-memory-release.schema.json` (`corpus_release_ref`) | Memory.md (always-loaded index) | — (canonical) | explicit-delete-only (legal-hold) |
| procedural | `PLAN` | `procedural-memory-bundle.schema.json` | skills / playbooks | — | `active_flag` (rollback, not delete) |

**topic_set / span / domain** — memory-mesh today expresses these *piecemeal*: topic via `slash-topic-memory-profile` (`active_topic_refs`, `topic_artifact_refs`), span via `valid_from`/`valid_to` / `expires_at`, domain via `.sourceos` `domain` + scope ordering (`run → agent → user → workspace → peer`) and `prophet-mesh-memory-scope`. ER-1 requires them as **one uniform envelope on every memory item** → GAP-ER-2.

**auto-dream ↔ promotion/forgetting** — the Claude auto-dream cycle is not a new mechanism; each phase is an
existing estate mechanism:

| auto-dream phase | estate mechanism | ER effect |
|---|---|---|
| Fork(isolation) | isolated worktree / a DECISION_CYCLE run in isolation (no shared-state write) | consolidation cycle proposes writes on the soft lane |
| Distill / Merge | memory-mesh `PromotionRule.summarization_strategy` | episodic `OBSERVATION` → semantic `GRAPH_ENTITY`/`FAIR_METADATA` |
| Conflict-Resolution | `PromotionRule.contradiction_policy` + temporal-retrieval-filter (most-recent-fact wins) | supersede stale entities; POLICY_CHECK gates the write |
| Prune (entropy control) | memory-mesh `ForgettingPolicy` (`decay_strategy`/`compaction`/`purge_conditions`) | demote/retire (retirement-not-destruction); emits AUDIT_EVENT |
| Index-Sync | openclaw MEMORY.md projection (`adapters/openclaw-memory-mesh`) | regenerate the Memory.md-style index over durable nodes |

## GAPs (filed as issues, @mdheller)

| GAP | What's missing | Home repo |
|---|---|---|
| **GAP-ER-1** | First-class `VectorChunk` contract binding a chunk → `FAIR_OBJECT` + the memory-scope envelope (memoryd stores a Qdrant point = vector+payload, no chunk↔object schema). | prophet-platform (memoryd) |
| **GAP-ER-2** | Uniform `(topic_set, span, domain)` memory-scoping envelope across the FSMS memory schemas (today piecemeal). | memory-mesh |
| **GAP-ER-3** | First-class versioned `DATASET_VERSION` entity so `PROVENANCE_RECORD depends_on DATASET_VERSION` is uniformly enforceable (today only provenance sha256 + embedding-carry-ref). | sourceos-model-carry |
| **GAP-ER-4** | Re-land policy-fabric#102 shared-state/live-activation decision on main so the `ACTION gated_by POLICY_CHECK` tooth is in force for shared-state writes at runtime (ties to ADR-0002 GAP-1 / #83). | policy-fabric |
| **GAP-ER-5** (live wiring) | Enforce the ER teeth at the runtime write path (receipt-gateway / capability-membrane) so an ACTION without POLICY_CHECK+AUDIT_EVENT, or a PROVENANCE_RECORD without DATASET_VERSION+MODEL_VERSION, is rejected in production — not only in this contract test. | prophet-workspace / prophet-platform |
