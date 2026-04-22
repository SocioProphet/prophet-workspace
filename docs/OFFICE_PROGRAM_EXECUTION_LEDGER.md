# Office Program Execution Ledger

This ledger turns the office/workspace program into an explicit multi-turn implementation plan.

The target is a world-class, fully agentic office and workspace stack with parity or better against:
- Microsoft Office / Microsoft 365 workflows
- Google Workspace workflows
- sovereign ODF-first SourceOS workflows

The program is split across:
- `prophet-workspace` — product semantics and capability contracts
- `prophet-platform` — cloud/runtime realization
- `source-os` — Linux and desktop realization
- `memory-mesh` — recall/writeback runtime
- `lampstand` — local desktop indexing/search
- `ontogenesis` — ontology and alignment layer

## Program phases

### Phase 0 — topology and doctrine

Goal:
- lock repo roles
- lock office doctrine
- lock cross-repo boundaries

Primary repo:
- `prophet-workspace`

Acceptance gate:
- repo matrix agreed
- office architecture agreed
- cross-repo responsibilities stated

### Phase 1 — product semantics and parity model

Goal:
- define what parity means against Microsoft Office, Google Workspace, and ODF-first sovereign workflows

Primary repo:
- `prophet-workspace`

Deliverables:
- office parity matrices
- product object model
- AI/workflow capability model
- admin/user semantics

Acceptance gate:
- product semantics can drive runtime contracts without ambiguity

### Phase 2 — runtime contracts and cloud office control

Goal:
- define the minimum cloud/runtime contract set for office documents, sessions, actions, receipts, and flows

Primary repo:
- `prophet-platform`

Deliverables:
- WOPI/runtime profile
- office document/action/receipt/flow schemas
- first service scaffolding

Acceptance gate:
- contracts exist for view/edit/save/lock/action/flow without product/runtime duplication

### Phase 3 — SourceOS desktop profile

Goal:
- realize the local-first office shell on SourceOS

Primary repo:
- `source-os`

Deliverables:
- LibreOffice profile
- MIME/font/template integration
- local smoke/parity surfaces
- cloud handoff behavior

Acceptance gate:
- SourceOS can claim a coherent desktop office profile

### Phase 4 — extraction, search, and graph grounding

Goal:
- make office content searchable and groundable across local and cloud contexts

Primary repos:
- `prophet-platform`
- `lampstand`
- `ontogenesis`

Deliverables:
- semantic unit extraction
- local search handoff
- graph boundary mappings
- permission-preserving indexing expectations

Acceptance gate:
- a document can be extracted, typed, indexed, and cited

### Phase 5 — memory-backed assistance

Goal:
- make office AI and workflow agents recall-aware and writeback-aware

Primary repos:
- `memory-mesh`
- `prophet-platform`
- `prophet-workspace`

Deliverables:
- recall-before-action path
- writeback-after-action path
- memory policy hooks
- office assistant continuity semantics

Acceptance gate:
- a grounded office action can retrieve permitted memory and emit writeback receipts

### Phase 6 — collaboration and cloud editing

Goal:
- provide cloud editing with saveback, versions, and conflict controls

Primary repo:
- `prophet-platform`

Deliverables:
- WOPI host path
- versions/locks/sessions
- comments/suggestions model
- preview/conversion path

Acceptance gate:
- open/edit/save/version in cloud editor works through platform contracts

### Phase 7 — workflow agents and studio

Goal:
- provide declarative and guided office/workspace flows

Primary repos:
- `prophet-workspace`
- `prophet-platform`

Deliverables:
- flow model
- starters/steps/approvals
- example automations
- audit/receipt linkage

Acceptance gate:
- a document-centered workflow can run end to end with approvals and receipts

### Phase 8 — parity corpus and release gates

Goal:
- make parity and regression measurable

Primary repos:
- `prophet-workspace`
- `prophet-platform`
- `source-os`

Deliverables:
- Microsoft corpus
- Google corpus
- ODF corpus
- parity result model
- regression/smoke gates

Acceptance gate:
- no office stack changes merge without parity evidence

## Initial sequencing for the next 98 turns

### Turns 1–10
- complete repo matrix
- complete office doctrine and product semantics
- settle cross-repo ownership

### Turns 11–25
- parity matrixes and object model in `prophet-workspace`
- runtime starter schemas and WOPI profile in `prophet-platform`
- SourceOS office profile stubs and config surfaces in `source-os`

### Turns 26–40
- extraction/indexing contracts
- memory and search integration contracts
- ontology/alignment surfaces for office semantic units

### Turns 41–60
- first WOPI service path
- first office action/receipt path
- first local and cloud office smoke flows

### Turns 61–80
- workflow studio surfaces
- memory-backed assistant flows
- spreadsheet and deck helper surfaces

### Turns 81–98
- parity corpus
- migration reporting
- admin policy surfaces
- release gates and regression checks

## Rule

Each implementation slice should clearly declare:
- which repo owns the semantics
- which repo owns the runtime
- which repo owns the host realization
- where memory/search/ontology hooks enter the slice
