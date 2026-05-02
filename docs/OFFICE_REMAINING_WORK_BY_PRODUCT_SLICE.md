# Office Remaining Work by Product Slice

This document tracks the remaining work to reach a world-class office and workspace product.

It is intentionally organized by product slices rather than repo-only slices.

## Slice A — Installed office shell correctness

Goal:
- installed `sourceos-office` must work as a real front door outside the repo tree

Remaining work:
- ensure install path stages all required helpers
- ensure `open`, `search`, `install`, and `verify` subcommands work in installed mode
- reduce repo-relative fallback assumptions

Primary repos:
- `SociOS-Linux/source-os`

## Slice B — Local office quality

Goal:
- credible local-first office workflow quality

Remaining work:
- richer template packs
- print/export fidelity
- stronger DOCX/XLSX/PPTX compatibility path
- more round-trip corpus coverage

Primary repos:
- `SociOS-Linux/source-os`
- `SocioProphet/prophet-workspace`

## Slice C — Cloud office collaboration

Goal:
- credible browser open/edit/save/version path

Remaining work:
- stronger WOPI behavior and backend integration
- comments/suggestions/version model completion
- cloud share/open path refinement

Primary repos:
- `SocioProphet/prophet-platform`
- `SocioProphet/prophet-workspace`

## Slice D — Sherlock fused discovery

Goal:
- one coherent discovery plane across local, workspace, memory, and ontology-aligned sources

Remaining work:
- richer normalized result fields and actions
- result fusion beyond platform-only placeholders
- local/cloud/memory source provenance surfacing
- product-facing search journeys and validation

Primary repos:
- `SocioProphet/prophet-platform`
- `SocioProphet/prophet-workspace`
- `SocioProphet/lampstand`
- `SocioProphet/memory-mesh`
- `SocioProphet/ontogenesis`
- `SocioProphet/sherlock-search`

## Slice E — Agentic office actions

Goal:
- make search and documents actionable, approval-aware, and evidence-backed

Remaining work:
- connect normalized result actions to real office/workspace actions
- add receipts and evidence paths
- policy-gated side effects for task creation / draft reply / summarize / rewrite

Primary repos:
- `SocioProphet/prophet-platform`
- `SocioProphet/prophet-workspace`

## Slice F — Google Workspace equivalent

Goal:
- parity beyond files alone

Remaining work:
- Drive-like object model and discovery
- comments/suggestions/revision path
- workflow automation equivalents
- cross-app discovery and search

Primary repos:
- `SocioProphet/prophet-workspace`
- `SocioProphet/prophet-platform`

## Slice G — Microsoft Office equivalent

Goal:
- parity beyond format compatibility alone

Remaining work:
- review/versioning path
- Word/Excel/PowerPoint workflow fidelity improvements
- migration/import reporting
- stronger installed/local/cloud transitions

Primary repos:
- `SocioProphet/prophet-workspace`
- `SocioProphet/prophet-platform`
- `SociOS-Linux/source-os`

## Slice H — Product acceptance and release gates

Goal:
- measure product-complete progress by user journey, not by script count

Remaining work:
- top user-journey acceptance harness
- merge gates by product slice
- clearer product-complete percentage tracking

Primary repos:
- `SocioProphet/prophet-workspace`
- `SocioProphet/prophet-platform`
- `SociOS-Linux/source-os`

## Product-complete posture

We should treat the remaining work as mostly productization, not architecture.

The major remaining gaps are not “where does this belong?” anymore.
They are:
- installed-path correctness
- collaboration quality
- fused discovery quality
- agentic action quality
- enterprise/workspace product completeness
