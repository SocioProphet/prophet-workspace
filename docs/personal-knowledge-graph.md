# Personal Knowledge Graph (the ego-scoped CSKG)

The **default graph structure for a person** — the seed the Memory Steward
builds over. It is not a new store or a parallel vocabulary: it is the
**person-scoped view of the CSKG** (Context/Semantic Knowledge Graph) this
workspace already models. Where a `ContextGraph` is anchored on a **workroom**,
a `PersonalContextGraph` is anchored on the **individual** (`selfRef`).

Contract: [`context-fabric/personal-context-graph.schema.json`](../contracts/workspace/context-fabric/personal-context-graph.schema.json)
· example: [`personal-context-graph.v0.1.example.json`](../contracts/workspace/context-fabric/personal-context-graph.v0.1.example.json)
· validate: `python3 tools/validate_personal_context_graph.py`.

## What it is

- **Anchor.** Exactly one `Self` node (`selfRef`) — the single-Self invariant.
- **Nodes** are CSKG nodes (contacts carry their `csKgNodeRef` here). The entity
  vocabulary a person is built from: `Self, Person, Place, Organization, Thing,
  Interest, Event, Document, Communication, Account`.
- **Edges** are `CSKGEdge {node1, relation, node2, provenance_refs,
  source_evidence_refs}`. The typed relations: `relatedTo, knows, homeTown,
  residesIn, attended, worksAt, memberOf, providerFor, owns, uses, interestedIn,
  skilledIn, participatedIn, authored, communicatedWith, hasAccount`.
- **Provenance.** `sourceRefs` are `WorkspaceSource` ids — the Layer-1 canonical
  objects each element was derived from. This makes citations real and makes
  retention actionable: when a `WorkspaceSource` is deleted per its
  `retentionPolicyRef`, its derived nodes/edges retract.
- **External links are reference-only.** A person-graph node may correspond to an
  entity in an external KG (general-purpose / social / domain / e-commerce), but
  that link crosses the membrane **only** as a `ProviderProjection`
  (`includedNodeRefs` + `withheldRefs` + `membraneDecisionRef`). The mesh
  *resolves/reads* the external entity for grounding; nothing private egresses.
- **Scope.** Governed by a `memoryScope` (default `relationship_context:approved`),
  owned by the **memory-steward** agent.

## Populating it: workspace records → CSKG

The runtime ingests canonical workspace objects and emits CSKG nodes/edges:

| WorkspaceSource | → node | → edge(s) |
|---|---|---|
| `contact` (person) | `Person` | `relatedTo` (family hint) / `knows`; `worksAt` if `organizationRef`; social `socialProfiles` → reference-only external projection |
| `contact` (organization) | `Organization` | — |
| `calendar-event` | `Event` | `participatedIn` (Self + attendees with `contactRef`) |
| `mail-message` | (correspondent `Person`) | `communicatedWith` |
| `office-artifact` | `Document` | `authored` |

Every emitted element carries `provenance_refs` = the originating
`WorkspaceSource` id + `source_evidence_refs`.

## Ownership split (contract-first)

This repo owns the **contract** only. Per the estate split:

- **prophet-workspace** (here) — the `PersonalContextGraph` contract + the
  record→CSKG mapping. No runtime, no deployment.
- **memory-mesh** — the **runtime**: reads `WorkspaceSource` objects, resolves
  `csKgNodeRef`, normalizes relations through the CSKG normalizer, and writes the
  managed HellGraph via `HELLGRAPH_URL`. Recall-before-action /
  writeback-after-action.
- **prophet-platform** — the **deployment**: HellGraph as a managed, durable
  graph service (StatefulSet + RocksDB PVC), local flash via TopoLVM on the edge,
  edge↔cloud-twin sync.
- **prophet-mesh** — the **consumer**: grounds retrieval on the person-graph.

The graph is a **Layer-2 derived store** — rebuildable from the Layer-1 canonical
objects, resident edge-first (privacy-high, per-person), never a source of truth.
