# Office Program Repo Matrix

This document records the effective repo split for the SourceOS office and workspace program.

It is intentionally practical: it covers the repos that are visible and relevant to this program in the current GitHub connector view.

## Primary repos

### `SocioProphet/prophet-workspace`

Role:
- workspace product semantics
- user/admin capability contracts
- office/workspace parity objectives
- product object model for docs, sheets, slides, files, collaboration, AI assistance, and workflow agents

Use for:
- architecture docs
- capability profiles
- parity matrixes
- product/backlog and UX semantics

### `SocioProphet/prophet-platform`

Role:
- cloud/runtime realization
- WOPI host and office session control
- extraction/indexing/orchestration services
- AI action and workflow runtime
- starter schemas and runtime contracts

Use for:
- runtime docs
- service scaffolding
- deployment-facing contracts
- cloud office control plane

### `SociOS-Linux/source-os`

Role:
- Linux and desktop realization
- LibreOffice profile and compatibility tuning
- MIME/font/template integration
- local extraction and parity smoke surfaces
- desktop shell and cloud handoff behavior

Use for:
- host profiles
- build surfaces
- config defaults
- local verification scripts

## First-class shared dependencies

### `SocioProphet/memory-mesh`

Role:
- canonical memory runtime
- recall-before-action
- writeback-after-action
- configurable retention and retrieval policy for office agents

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

### `SocioProphet/ontogenesis`

Role:
- canonical ontology and alignment framework
- JSON-LD boundary/context surface
- provenance-aware semantic mapping and alignment

Use for:
- office semantic unit typing
- vocabulary alignment across ODF / OOXML / Google exports / local runtime objects
- graph boundary semantics and mappings

## Secondary/supporting repos

### `SocioProphet/prophet-platform-standards`

Use later for:
- promoted platform standards once office runtime contracts stabilize

Do not use first for:
- product semantics
- initial service/domain architecture

### `SocioProphet/socioprophet-agent-standards`

Use later for:
- cross-domain action / receipt / workflow record generalization if the office models mature enough to promote

Do not use first for:
- the initial office program slice

### `SocioProphet/socios-web`
### `SociOS-Linux/socioslinux-web`

Use later for:
- public docs
- product marketing/demo surfaces
- user/admin web presentation

Do not use first for:
- core office architecture or runtime contracts

## Likely ignore for this program unless requirements change

### `SociOS-Linux/socios-scripts`
- only use if it already contains host bootstrap patterns we can reuse

### `SociOS-Linux/socios-alarm-builder`
- unrelated to office/workspace scope

### `SociOS-Linux/artwork`
- branding only

### `SociOS-Linux/BPF-Linux`
- unrelated to office/workspace scope

## Notes on org visibility

The current connector view clearly exposes `SocioProphet` and `SociOS-Linux` repos relevant to the office program.

No distinct `SourceOS-Linux` org topology is clearly exposed in this pass beyond the active `SociOS-Linux/source-os` realization path, so the office program should treat `SociOS-Linux/source-os` as the effective SourceOS host integration home until a different active org/repo boundary is confirmed.

## Program rule

No new repo should be created for the office/workspace program until the primary and first-class dependency repos above prove structurally insufficient.
