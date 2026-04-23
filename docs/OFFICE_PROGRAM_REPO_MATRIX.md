# Office Program Repo Matrix

This document records the effective repo split for the SourceOS office and workspace program.

It is intentionally practical and based on the currently visible repositories in the live GitHub connector view.

## Primary repos

### `SocioProphet/prophet-workspace`

Role:
- workspace product semantics
- user/admin capability contracts
- office/workspace parity objectives
- product object model for docs, sheets, slides, files, collaboration, AI assistance, and workflow agents

Use for:
- office/workspace architecture docs
- capability profiles and matrices
- product backlog and UX semantics
- admin and user surface expectations

### `SocioProphet/prophet-platform`

Role:
- cloud/runtime realization
- WOPI host and office session control
- extraction/indexing/orchestration services
- AI action runtime and receipts
- workflow runtime and deployment topology

Use for:
- service scaffolding
- runtime docs
- runtime schemas and contracts
- deployment-facing architecture

### `SociOS-Linux/source-os`

Role:
- Linux and desktop realization
- LibreOffice and local office profile integration
- MIME/font/template integration
- local smoke/parity surfaces
- desktop shell and cloud handoff behavior

Use for:
- host profiles
- desktop integration
- local config and build surfaces
- local verification and handoff helpers

## First-class shared dependencies

### `SocioProphet/memory-mesh`

Role:
- canonical memory runtime
- recall-before-action
- writeback-after-action
- configurable storage, retrieval, and retention policy for office agents

Use for:
- office assistant memory
- workflow-agent memory
- user/project continuity

### `SocioProphet/lampstand`

Role:
- canonical desktop indexing and local search runtime
- inspectable local file discovery, health, and stats

Use for:
- local office file discovery
- desktop search handoff
- SourceOS office shell launch/search behavior

### `SocioProphet/sherlock-search`

Role:
- higher-level search and discovery layer
- cross-source query planning, result fusion, and ranking
- product-level discovery semantics across local, cloud, and memory sources

Use for:
- federating Lampstand, platform indexes, and memory retrieval
- office/workspace discovery UX beyond one local indexer
- search orchestration across documents, files, tasks, chat, mail, and projects

### `SocioProphet/ontogenesis`

Role:
- canonical ontology and alignment framework
- JSON-LD context and graph boundary surfaces
- provenance-aware semantic mapping and schema alignment

Use for:
- office semantic unit typing
- vocabulary alignment across ODF / OOXML / Google exports / runtime objects
- graph boundary semantics and mappings

## Secondary/supporting repos

### `SocioProphet/prophet-platform-standards`

Use later for:
- promoted platform standards once office runtime contracts stabilize

Do not use first for:
- product semantics
- initial office runtime/service architecture

### `SocioProphet/socioprophet-agent-standards`

Use later for:
- cross-domain action / receipt / workflow record generalization if office models mature enough to promote

Do not use first for:
- initial office/workspace program slices

### `SocioProphet/socios-web`
### `SociOS-Linux/socioslinux-web`

Use later for:
- public docs
- product demos
- user/admin web presentation

Do not use first for:
- core office architecture or runtime contracts

## Peripheral / not primary for this program right now

### `SociOS-Linux/socios-scripts`
- only use if we need an existing bootstrap pattern we cannot reasonably place in `source-os`

### `SociOS-Linux/socios-alarm-builder`
- not an office/workspace program primary

### `SociOS-Linux/artwork`
- branding only

### `SociOS-Linux/BPF-Linux`
- not a primary office/workspace lane

## Note on org visibility

The current connector view clearly exposes the relevant office/workspace repos in `SocioProphet` and `SociOS-Linux`.

A distinct active `SourceOS-Linux` org topology is not clearly exposed in this pass beyond the active `SociOS-Linux/source-os` path, so this program should treat `SociOS-Linux/source-os` as the effective SourceOS host integration home until a different active boundary is confirmed.

## Rule

No new repo should be created for the office/workspace program until the primary and first-class dependency repos above prove structurally insufficient.
