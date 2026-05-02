# Prophet Workspace Office Plane

The Office Plane is the workspace capability layer for documents, spreadsheets, slide decks, PDFs, mail drafts, calendar items, task lists, notes, and media assets.

It extends the existing `prophet-workspace` model rather than replacing it. Professional Workrooms remain the product spine; Office artifacts become workroom-bound objects with policy, evidence, review, and AgentPlane lineage.

## Why this belongs here

`prophet-workspace` owns workspace product semantics and capability contracts for mail, calendar, drive, docs, chat, and meeting surfaces. The Office Plane is therefore a product/domain concern here, while runtime deployment remains in `prophet-platform` and local execution remains in SourceOS/Agent Machine.

## Core contracts

| Contract | Purpose |
|---|---|
| `contracts/workspace/professional-workroom.schema.json` | Workroom spine: context, policy, obligations, agent runs, evidence, tasks, and Office artifact refs. |
| `contracts/workspace/office-artifact.schema.json` | Workspace-bound office artifact: docs, sheets, slides, PDFs, mail drafts, calendar items, task lists, notes, and media. |

## Artifact types

`OfficeArtifact.artifactType` supports:

- `document`
- `spreadsheet`
- `slide-deck`
- `pdf`
- `mail-draft`
- `calendar-item`
- `task-list`
- `note`
- `media-asset`

## Backends

The Office Plane is backend-abstract. Agents and users request capabilities; the Workspace chooses the backend according to policy, deployment mode, user preference, and availability.

| Backend | Intended role |
|---|---|
| LibreOffice | SourceOS local-first default for headless generation, inspection, render, and conversion. |
| Collabora | Browser-collaboration backend for LibreOffice-compatible editing and WOPI-style integration. |
| ONLYOFFICE | Optional document-builder/editor backend, especially for DOCX/XLSX/PPTX generation flows. |
| Microsoft Graph / Office 365 | External compatibility adapter, not the core authority. |
| Google Workspace | External compatibility adapter. |
| SourceOS Native | Future native document surfaces and app doors. |

## SourceOS Agent Machine alignment

Local generation should use the Agent Machine Local Data Plane:

| Purpose | Host path | Agent path |
|---|---|---|
| Workroom output | `~/Documents/SourceOS/agent-output` | `/workspace/output` |
| Browser downloads | `~/Downloads/SourceOS/agent-downloads` | `/workspace/downloads` |
| Code/templates | `~/dev` or declared template root | `/workspace/dev` |

Agents should not raw-mount whole `~/Documents`, `~/Downloads`, browser profiles, mail stores, Notes databases, Photos libraries, keychains, or cloud credential directories.

## Workroom binding

Professional Workrooms now support `officeArtifactRefs` at the workroom level and `officeArtifactRef` at the task level.

A generated deck, spreadsheet, report, PDF, or mail draft should appear as:

```text
ProfessionalWorkroom.officeArtifactRefs[] -> OfficeArtifact.storageRef -> evidenceRefs[] -> AgentPlane run/evidence
```

This keeps Office artifacts inside the same policy and evidence loop as workroom context, tasks, and agent runs.

## Side-effect posture

Creating or converting an Office artifact is a normal agent action.

Sending email, publishing a file externally, editing a shared calendar, or writing to an external Office 365/Google Workspace surface is a side effect and should require explicit policy approval unless the workroom policy says otherwise.

Default mail posture:

1. Generate mail draft.
2. Attach or link Office artifacts.
3. Record evidence.
4. Require human review before send.

## First implementation slice

1. `OfficeArtifact` contract and example.
2. Professional Workroom binding to `officeArtifactRefs`.
3. Validator coverage for both contracts.
4. SourceOS CLI follow-up: `sourceosctl office ...` using LibreOffice locally.
5. AgentPlane follow-up: `OfficeArtifactEvidence` or a general artifact evidence binding.
6. AgentTerm follow-up: `/office create doc`, `/office create sheet`, `/office create deck`, `/office convert`, `/office inspect`.

## Non-goals

- This repo does not own final cluster deployment topology.
- This repo does not vendor LibreOffice, Collabora, ONLYOFFICE, Microsoft 365, or Google Workspace.
- This repo does not implement raw Mac Notes, Photos, Reminders, or Voice Memos database access.
- This repo does not grant send-mail authority by default.
