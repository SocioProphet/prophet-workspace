# Lattice Studio Workspace Integration Contract

`prophet-workspace` owns the open office/workspace product semantics that run over `SocioProphet/prophet-platform`. Lattice Studio must integrate with this work directly instead of treating office files as loose uploads or external links.

## Product target

Lattice Studio should feel like NotebookLM-class source-grounded synthesis, but with governed executable workbench infrastructure and full office/workspace integration.

The target loop is:

```text
collect workspace sources -> bind catalog/runtime/policy -> ask/summarize/compare -> execute notebook/runtime -> emit evidence -> draft/publish/share through workspace surfaces
```

## Required workspace surfaces

The integration must cover these Prophet Workspace surfaces:

- mail
- calendar
- contacts
- file storage and sync
- collaborative documents
- collaborative sheets
- collaborative slides
- chat and rooms
- meetings and calls
- admin, audit, policy, and search

## Lattice source model

Workspace objects must be usable as governed Lattice Studio sources:

```text
WorkspaceSource
  -> SourceBinding
  -> NotebookSession / NotebookSurfaceSpawnRequest
  -> EvidenceBundle
  -> WorkspacePublication / WorkspaceShareReceipt
```

A workspace source may represent:

- a mail message or thread;
- a calendar event or meeting record;
- a contact or organization record;
- a Drive/WebDAV file;
- a document, sheet, or slide deck;
- a chat room, thread, or message set;
- a meeting transcript, recording, or artifact bundle;
- an admin/audit/policy record.

## Required source metadata

Every workspace source exposed to Lattice Studio must carry:

```text
source id
workspace surface
owner or authority scope
project/group/org scope
source URI or backend reference
content digest where applicable
version or modified timestamp
access policy reference
retention policy reference
evidence correlation id
```

## Office artifact workflow

Lattice Studio must support this office workflow:

1. Import or bind a workspace document, sheet, slide deck, mail thread, meeting artifact, or chat thread as a source.
2. Attach the source to a project notebook/workbench.
3. Bind the workbench to a RuntimeAsset and policy.
4. Ask questions, summarize, compare, classify, extract entities, build tables, produce charts, or execute notebook code against bound data.
5. Emit an evidence record that ties output to source ids, runtime ids, policy ids, and session ids.
6. Publish or draft the result back into workspace surfaces as a document, sheet, slide deck, message, mail draft, or meeting packet.

## Google Workspace MCP relationship

`SocioProphet/google_workspace_mcp` can be used as an adapter implementation for Google Workspace-backed office surfaces. It is not the canonical product contract.

The canonical product contract lives here in `prophet-workspace` and should remain backend-neutral. Google Workspace, LibreOffice/Collabora, Nextcloud, Matrix, JMAP, CalDAV, CardDAV, WebDAV, WebRTC, and other implementations should plug into this contract.

## Lattice Studio binding requirements

Lattice Studio must be able to consume workspace sources through:

- `WorkspaceSource` records;
- `WorkspaceSourceBinding` records;
- `NotebookSession.catalogInputs[]` or a successor `sourceInputs[]` field;
- `EvidenceBundle` / `NotebookSessionEvidence` correlation ids;
- `PlatformAssetRecord` conversion for search, topics, governance, policy, and contract enrichment.

## Evidence requirements

Every office/workspace action triggered from Lattice Studio must emit a receipt:

```text
WorkspaceActionReceipt
```

A receipt must record:

```text
action id
actor id
workspace surface
action type
input source ids
output artifact ids
runtime asset id where applicable
notebook session id where applicable
policy reference
evidence correlation id
created timestamp
content digest or output digest where applicable
```

## Policy requirements

Workspace integration must respect:

- source visibility and sharing policy;
- project/group/org scope;
- export restrictions;
- data retention and deletion policy;
- personal/private source boundaries;
- agent access policy;
- publication approval policy;
- audit requirements.

## Minimum implementation slice

The first demo-grade slice should include:

1. WorkspaceSource fixture for a document.
2. WorkspaceSource fixture for a sheet or dataset-backed spreadsheet.
3. WorkspaceSource fixture for a slide deck/report.
4. WorkspaceSourceBinding into a Lattice Studio NotebookSession.
5. WorkspaceActionReceipt emitted for a generated document/report.
6. PlatformAssetRecord conversion for workspace source and generated output.
7. Search/governance enrichment hooks through Prophet Platform.

## Dependency direction

- `prophet-workspace` owns office/workspace product semantics and backend-neutral source/action contracts.
- `prophet-platform` owns ingestion, assignment, policy binding, Lattice Studio orchestration, search/governance enrichment, and evidence correlation.
- `lattice-forge` owns reproducible RuntimeAsset construction.
- `google_workspace_mcp` may provide Google Workspace adapter implementation.

## Doctrine

Office work is not outside the notebook/workbench. It is part of the source, evidence, publication, and collaboration fabric.

Lattice Studio should be a governed workbench for thinking, computing, drafting, publishing, and collaborating across workspace artifacts.
