# Sherlock Search Query Model

This document defines the product-level query model for Sherlock Search in the office/workspace program.

Sherlock Search is the federated discovery layer above:
- Lampstand local desktop indexing
- platform workspace/cloud indexes
- memory-mesh recall
- ontogenesis-backed semantic alignment

## Query goals

A single product-facing query should be able to express:
- local file discovery
- cloud/workspace discovery
- memory-augmented discovery
- mixed discovery across those sources
- document-first and workspace-entity-first discovery

## Core query object

```yaml
query_id: string
actor_id: string
text: string
mode: KEYWORD | SEMANTIC | HYBRID
scope:
  local_desktop: bool
  cloud_workspace: bool
  memory: bool
  include_entities: [DOCUMENT | SHEET | SLIDE | COMMENT | TASK | CHAT | MAIL | MEETING | PROJECT]
filters:
  owners: [string]
  mime_types: [string]
  canonical_formats: [ODF | OOXML | PDF | OTHER]
  tags: [string]
  created_after: timestamp?
  created_before: timestamp?
  modified_after: timestamp?
  modified_before: timestamp?
  project_refs: [string]
  permission_refs: [string]
ranking:
  prefer_local: bool
  prefer_recent: bool
  prefer_memory_hits: bool
  prefer_project_hits: bool
limit: integer
```

## Modes

### `KEYWORD`
Use exact lexical matching or file-name / field matching where appropriate.

### `SEMANTIC`
Use semantic retrieval over indexed semantic units, memory, and graph-bound workspace context.

### `HYBRID`
Fuse lexical and semantic signals and rank the combined result set.

## Query families

### Local file discovery
Examples:
- "find the contract draft on my desktop"
- "show spreadsheets modified this week"

Primary backend:
- Lampstand

### Workspace discovery
Examples:
- "find decks related to Q2 pipeline review"
- "show project docs with action items"

Primary backend:
- platform/FogGraph indexes

### Memory-augmented discovery
Examples:
- "find the doc we used for the last board summary"
- "show notes tied to the Alpha project kickoff"

Primary backend:
- memory-mesh plus platform indexes

### Hybrid office discovery
Examples:
- "find the latest budget workbook and related meeting notes"
- "show local drafts plus cloud versions of the proposal"

Primary backends:
- Lampstand + platform indexes + memory as available

## Product rule

Sherlock should not expose source-specific complexity to end users.

The user expresses intent once. Sherlock decides:
- which backends are relevant
- how to decompose the query
- how to rank and merge results

## Cross-repo mapping

- `lampstand` = local search backend
- `prophet-platform` = cloud/workspace index backend
- `memory-mesh` = recall backend
- `ontogenesis` = semantic alignment and boundary mapping
