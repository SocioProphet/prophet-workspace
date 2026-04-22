# Workspace Office Product Architecture

## Purpose

This document defines the workspace-domain architecture for the SourceOS office suite program.

The product goal is not merely LibreOffice compatibility. The goal is a sovereign office and workspace suite with measurable parity for:
- Microsoft Office / Microsoft 365 office workflows
- Google Workspace office workflows
- SourceOS sovereign ODF-first workflows

## Repo boundary

`prophet-workspace` owns:
- workspace product semantics
- capability contracts for docs, sheets, slides, drive, mail, chat, meetings, and AI assistance
- user-facing and admin-facing workspace UX expectations
- product-level parity objectives and product object model
- adapter contract expectations for pluggable backends

`prophet-workspace` does not own:
- cluster deployment topology
- final runtime wiring
- Linux host integration

Those belong in `SocioProphet/prophet-platform` and `SociOS-Linux/source-os`.

## Product layers

1. Workspace surfaces
   - docs, sheets, slides
   - drive/files
   - mail, calendar, contacts
   - chat, rooms, meetings
   - admin, audit, search

2. Workspace intelligence
   - grounded drafting
   - document and folder Q&A
   - spreadsheet analysis
   - deck generation and summarization
   - workflow agents and no-code flows
   - memory-backed recall and project/user continuity
   - desktop and cloud search integration
   - ontology-aware document and workspace understanding

3. Product policy and control
   - sharing rules
   - retention and audit
   - model access policy
   - action approval and receipts

## Cross-repo integration

### With `prophet-platform`

`prophet-platform` should provide the runtime and deployment realization for:
- WOPI host and document session control
- office document records and AI action receipts
- office context extraction, indexing, and orchestration services
- cloud editing, preview, conversion, and workflow runtime
- memory-mesh integration for recall-before-action and writeback-after-action flows
- ontogenesis-aware semantic alignment surfaces for extracted document and workspace context

### With `source-os`

`source-os` should provide the Linux and desktop realization for:
- LibreOffice defaults and compatibility profile
- local extraction and smoke tests
- MIME, font, and template integration
- local-first office shell behavior
- Lampstand-backed desktop file and document discovery
- local memory-mesh hooks where policy allows desktop recall and writeback
- local metadata and semantic extraction handoff into ontogenesis-aligned structures

### With `memory-mesh`

`SocioProphet/memory-mesh` should provide the canonical memory runtime for:
- user and project memory
- recall-before-draft / recall-before-rewrite flows
- writeback-after-action and writeback-after-receipt flows
- configurable storage and retrieval policies for office agents

### With `lampstand`

`SocioProphet/lampstand` should provide the canonical desktop indexing and search runtime for:
- local office file discovery
- desktop search handoff into SourceOS office surfaces
- inspectable local health / stats / indexing state for office documents

### With `ontogenesis`

`SocioProphet/ontogenesis` should provide the canonical ontology and alignment framework for:
- office document semantic unit typing and normalization
- mappings between ODF, OOXML, Google Workspace exports, and local product vocabulary
- JSON-LD context and graph boundary surfaces for office/workspace records
- provenance-aware alignment of document, comment, suggestion, task, and workflow entities
- gradual semantic normalization rather than pretending all external office vocabularies match cleanly

## Product capability families

- writer/docs parity
- spreadsheet parity
- slide/deck parity
- file and drive parity
- collaboration parity
- migration and parity scoring
- AI assistance and workflow parity
- memory and recall parity
- local and cloud search parity
- ontology and alignment parity

## Immediate next step

The first implementation slice should define:
- office document object model
- AI action and receipt model
- workspace flow record model
- SourceOS desktop office profile
- FogStack / platform WOPI and cloud office runtime profile
- memory-mesh binding expectations for office AI
- lampstand binding expectations for local office search
- ontogenesis binding expectations for semantic alignment and graph boundaries
