# Office Product Object Model

This document defines the product-level object model for the SourceOS office and workspace suite.

The purpose is to separate product semantics from runtime realization.

## Core objects

### OfficeDocument

Represents a user-facing document object regardless of source format.

Examples:
- word processing document
- spreadsheet workbook
- slide deck
- PDF-backed record

Key concerns:
- canonical format
- source provider
- owner and permissions
- versions
- cloud/local editor binding
- migration status

### SemanticUnit

Represents a typed semantic fragment derived from an office document or workspace artifact.

Examples:
- paragraph
- heading
- table
- sheet
- cell range
- formula
- chart
- slide
- speaker note
- comment
- suggestion

Key concerns:
- type
- source version
- path within artifact
- text or structure payload
- indexability
- provenance

### OfficeAction

Represents a structured, proposed, or applied office mutation or derived action.

Examples:
- rewrite section
- summarize document
- create formula
- create chart
- add comment
- generate slide outline
- draft email from office context

Key concerns:
- action type
- target object / target region
- prompt and grounding
- approval state
- proposed change
- receipt linkage

### OfficeReceipt

Represents the evidence object for an applied or attempted office action.

Key concerns:
- actor
- model used
- tools used
- sources used
- policy checks
- before/after linkage
- created version
- status

### WorkspaceFlow

Represents a starter/step workflow that automates office or workspace behavior.

Examples:
- new project file -> summarize -> task creation -> chat notify
- meeting transcript -> summary -> follow-up draft

Key concerns:
- starter
- steps
- tools
- approvals
- schedule
- execution log

### MemoryBinding

Represents how office objects connect to memory recall and writeback.

Key concerns:
- recall-before-action
- writeback-after-action
- retention policy
- user/project scope

### SearchBinding

Represents how office objects connect to local and cloud discovery.

Key concerns:
- local desktop search handoff
- cloud workspace search
- permission-aware retrieval
- source of indexing truth

### OntologyBinding

Represents how office objects connect to semantic alignment.

Key concerns:
- JSON-LD boundary
- ontology term mapping
- provenance-aware normalization
- external schema alignment

## Product rule

These objects belong to the product/domain layer.

Runtime schemas in `prophet-platform` and host profiles in `source-os` should realize these objects, not redefine the product semantics from scratch.
