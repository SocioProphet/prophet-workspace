# Office Product Acceptance Matrix

This document records the product-complete acceptance matrix for the SourceOS office and workspace program.

The target is not “some office tooling on Linux.” The target is a world-class Linux-native equivalent for:
- macOS-quality desktop office workflows
- Microsoft Office / Microsoft 365 workflows
- Google Workspace workflows
- sovereign ODF-first local-first workflows

## Acceptance classes

- `FOUNDATION` — required for credible product substrate
- `PARITY` — required for competitive day-one product behavior
- `WORLD_CLASS` — required for premium product quality and trust

## Acceptance domains

### 1. Desktop office shell

Required outcomes:
- open office files from file manager and desktop entry
- local/cloud mode handoff is explicit and reliable
- installed `sourceos-office` front door works outside the repo tree
- MIME defaults and launcher behavior are coherent
- local search-to-open flow works from installed shell

Status:
- foundation: in progress
- parity: not complete
- world-class: not complete

### 2. Local office editing

Required outcomes:
- ODF-first local editing
- DOCX/XLSX/PPTX interoperability path
- font substitution behavior
- print/export/PDF path
- templates for sovereign/interoperability workflows
- round-trip smoke coverage

Status:
- foundation: in progress
- parity: not complete
- world-class: not complete

### 3. Cloud office editing

Required outcomes:
- browser open/edit/save flow
- document locks and writeback
- version history
- comments/suggestions path
- share/open via cloud editor

Status:
- foundation: in progress
- parity: not complete
- world-class: not complete

### 4. Workspace discovery

Required outcomes:
- local discovery via Lampstand
- cloud/workspace discovery via platform indexes
- federated search semantics via Sherlock
- permission-aware result filtering
- snippets, URIs, and actions on normalized results

Status:
- foundation: in progress
- parity: in progress
- world-class: not complete

### 5. Memory-aware assistance

Required outcomes:
- recall-before-action
- writeback-after-action
- project/user continuity
- grounded office search and drafting

Status:
- foundation: partial
- parity: not complete
- world-class: not complete

### 6. Agentic office actions

Required outcomes:
- summarize / rewrite / create-task / draft-reply actions
- approval-aware execution
- receipts and evidence
- version-safe application

Status:
- foundation: partial
- parity: not complete
- world-class: not complete

### 7. Google Workspace equivalent

Required outcomes:
- Docs/Sheets/Slides artifact compatibility
- Drive-like object/discovery/share model
- workflow/automation equivalent
- comments/suggestions/revisions parity
- cross-app search/discovery

Status:
- foundation: partial
- parity: not complete
- world-class: not complete

### 8. Microsoft Office equivalent

Required outcomes:
- Word/Excel/PowerPoint workflow parity
- comments/review/versioning path
- desktop/local/cloud transitions
- migration and compatibility reporting

Status:
- foundation: partial
- parity: not complete
- world-class: not complete

### 9. Admin/policy/trust

Required outcomes:
- policy-aware side effects
- search/result permission controls
- auditability and receipts
- stable trust boundaries for export/share/publish

Status:
- foundation: in progress
- parity: not complete
- world-class: not complete

### 10. Product polish

Required outcomes:
- install and update coherence
- bounded desktop polish
- low-friction first-run workflows
- fewer script-level assumptions leaking into installed paths

Status:
- foundation: in progress
- parity: not complete
- world-class: not complete

## Product-complete checkpoint rule

We should not measure completion only by merged docs, schemas, or helper scripts.

A domain is only counted as materially complete when:
- the user-facing workflow exists,
- the installed path works,
- the expected side effects are policy-safe,
- and the behavior is covered by repeatable validation.
