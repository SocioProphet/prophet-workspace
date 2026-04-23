# Sherlock Search Result Model

This document defines the product-level result model for Sherlock Search in the office/workspace program.

The result model should let Sherlock return a fused result set from:
- Lampstand local desktop search
- platform/FogGraph workspace search
- memory-mesh recall
- ontogenesis-aligned semantic units and entities

## Core result object

```yaml
result_id: string
source: LAMPSTAND | PLATFORM | MEMORY | MIXED
entity_type: DOCUMENT | SHEET | SLIDE | COMMENT | TASK | CHAT | MAIL | MEETING | PROJECT | MEMORY_NOTE
title: string
snippet: string?
path_or_uri: string?
canonical_format: ODF | OOXML | PDF | OTHER?
source_format: string?
owner_ref: string?
project_refs: [string]
permission_ref: string?
score:
  lexical: float?
  semantic: float?
  memory: float?
  final: float
highlights:
  matched_terms: [string]
  semantic_units: [string]
backlinks:
  related_documents: [string]
  related_tasks: [string]
  related_chats: [string]
  related_meetings: [string]
actions:
  open_local: bool
  open_cloud: bool
  summarize: bool
  create_task: bool
  draft_reply: bool
```

## Result families

### Local file result
Used when Lampstand is the primary source.

Key expectations:
- local filesystem path
- desktop-open action
- local metadata confidence
- local index health available separately

### Workspace object result
Used when the platform/FogGraph index is the primary source.

Key expectations:
- workspace object URI or ID
- permission-aware open action
- cloud-open action where relevant
- related comments/tasks/chats where appropriate

### Memory-augmented result
Used when memory-mesh contributes recall evidence.

Key expectations:
- recall snippet or rationale
- originating memory binding reference
- explicit provenance back to source documents or workspace entities

### Mixed result
Used when Sherlock fuses multiple sources.

Key expectations:
- stable result object with one final score
- visible provenance of contributing sources
- merged actions that remain permission-safe

## Product rules

1. Results must preserve provenance.
2. Results must preserve permission boundaries.
3. Results should surface actions, not only links.
4. Mixed results should expose enough source detail for debugging and trust.

## Office/workspace implication

For the office program, the result model should support:
- open local document
- open cloud document
- summarize result
- jump to related tasks/comments/meetings
- draft from result context
- compare local vs cloud copies when both exist

## Cross-repo mapping

- `lampstand` contributes local discovery records
- `prophet-platform` contributes workspace objects and actions
- `memory-mesh` contributes recall augmentation
- `ontogenesis` contributes semantic normalization and aligned entity typing
