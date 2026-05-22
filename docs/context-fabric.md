# Workspace Context Fabric

## Purpose

Workspace Context Fabric is the Prophet Workspace domain layer for governed cross-provider AI context.

It extends Professional Workrooms with explicit references for imported conversations, normalized context graphs, outbound provider projections, share grants, memory candidates, and runtime evidence bindings.

```text
ProfessionalWorkroom
  -> ContextGraph
  -> WorkspaceContextRuntimeBinding
  -> provider imports and projections
  -> share grants
  -> memory candidates
  -> platform evidence receipts
```

## Repository boundary

`prophet-workspace` owns product/domain semantics and user-facing workspace contracts. Runtime services and deployment remain in `prophet-platform`. Execution evidence remains in `agentplane`. Durable memory promotion remains in `memory-mesh`. Agent identity and capability references remain in `agent-registry`.

## Core contracts

The v0.1 surface adds:

- `context-graph.schema.json` — workroom-bound semantic graph reference object.
- `provider-import.schema.json` — inbound provider/shared-link/manual-paste capture.
- `provider-projection.schema.json` — outbound provider-compatible view compiled under policy.
- `share-grant.schema.json` — workspace access grant over a projection.
- `memory-candidate.schema.json` — reviewable pre-memory claim extracted from context.
- `workspace-context-runtime-binding.schema.json` — binding object joining workspace, provider, memory, execution, policy, and evidence refs.

## v0 invariants

1. Imported provider context is workroom-bound.
2. Provider projections are explicit objects, not implicit side effects.
3. Memory candidates are reviewable and do not imply durable writeback.
4. Runtime actions should reference platform evidence and policy decisions.
5. External providers receive compiled projections, not the canonical workspace graph.

## First slice

The first slice is contract-only. It creates the domain objects and validator needed for later runtime, execution, authority, and memory integration work.
