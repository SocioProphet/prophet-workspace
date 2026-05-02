# Office Top User Journeys

This document records the top user journeys that must work before we can credibly claim a world-class office and workspace product.

These are product-complete journeys, not repo-complete tasks.

## Status classes

- `NOT_STARTED`
- `SUBSTRATE_ONLY`
- `PARTIAL_PRODUCT`
- `PRODUCT_READY`

## 1. Open a local office file from the desktop shell

User intent:
- open a local DOCX/ODT/XLSX/PPTX from the file manager or desktop entry

Must prove:
- installed launcher works outside repo tree
- MIME defaults are coherent
- local open path is explicit and reliable

Current status:
- `PARTIAL_PRODUCT`

## 2. Search locally and open the result

User intent:
- search for a local document and open it immediately

Must prove:
- Lampstand-backed discovery works
- installed search/open path works
- installed front door resolves helpers correctly

Current status:
- `PARTIAL_PRODUCT`

## 3. Open in cloud mode from the installed shell

User intent:
- open a local file in cloud/editor mode from the installed office shell

Must prove:
- installed front door resolves cloud handoff helper correctly
- returned handoff is stable and usable

Current status:
- `PARTIAL_PRODUCT`

## 4. Create and use sovereign templates

User intent:
- start from SourceOS sovereign office templates and produce a real artifact

Must prove:
- templates are installed and discoverable
- print/export path works
- template journey is not just a placeholder file

Current status:
- `SUBSTRATE_ONLY`

## 5. Edit in browser, save, and recover versions

User intent:
- open a document in the cloud editor, save, and inspect versions

Must prove:
- WOPI/session/writeback path works
- version history is materialized
- cloud edit path is not stub-only

Current status:
- `SUBSTRATE_ONLY`

## 6. Review with comments/suggestions

User intent:
- collaborate with comments, suggestions, and revision history

Must prove:
- comments/review model exists end-to-end
- user-facing workflow works for at least one document type

Current status:
- `NOT_STARTED`

## 7. Search workspace and get useful normalized results

User intent:
- search workspace documents, tasks, chat, and project artifacts from one query

Must prove:
- Sherlock semantics apply
- result provenance is visible
- normalized results have snippet, URI, and action metadata

Current status:
- `PARTIAL_PRODUCT`

## 8. Search with policy-safe academy/workspace visibility

User intent:
- only see what the actor is allowed to see

Must prove:
- policy-aware search filtering works
- workspace/jurisdiction/actor context matters

Current status:
- `PARTIAL_PRODUCT`

## 9. Summarize or rewrite from search/document context

User intent:
- use one action from a search result or document context, such as summarize or rewrite

Must prove:
- action is grounded
- action is policy-safe
- action emits a receipt/evidence path

Current status:
- `NOT_STARTED`

## 10. Create a task or draft reply from a result

User intent:
- turn discovered content into the next workflow step

Must prove:
- action-bearing search result path works end-to-end
- task/draft side effects are governed

Current status:
- `NOT_STARTED`

## 11. Migrate a Microsoft Office corpus

User intent:
- import an existing Office corpus and understand compatibility risk

Must prove:
- corpus scan exists
- compatibility output is useful
- migration reporting is not format-only

Current status:
- `NOT_STARTED`

## 12. Migrate a Google Workspace corpus

User intent:
- bring over Docs/Sheets/Slides/Drive-oriented work and keep it usable

Must prove:
- Google export/model compatibility path exists
- Drive-like discovery and cross-artifact search exist

Current status:
- `NOT_STARTED`

## 13. Install the office shell and verify it in one command

User intent:
- get the office shell into a usable state with one front-door command

Must prove:
- install path stages launcher, MIME, helpers, and office front door
- verification path is explicit and reliable

Current status:
- `PARTIAL_PRODUCT`

## 14. Use the office shell as part of a professional workroom

User intent:
- use office artifacts, tasks, and evidence together inside a professional workspace surface

Must prove:
- office artifacts are first-class workroom objects
- references between workroom, tasks, and office artifacts are valid

Current status:
- `PARTIAL_PRODUCT`

## 15. Run one end-to-end “real work” flow

User intent:
- search for a document, open it, summarize it, create a task, and save the result in the workspace

Must prove:
- discovery, open, action, and persistence are all connected
- this feels like one product, not a collection of tools

Current status:
- `NOT_STARTED`

## Rule

A world-class claim requires at least the top local, cloud, search, collaboration, and action journeys to be `PRODUCT_READY`, not merely scaffolded.
