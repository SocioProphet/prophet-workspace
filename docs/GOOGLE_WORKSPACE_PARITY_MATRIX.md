# Google Workspace Parity Matrix

This matrix defines the product-level parity targets for Google Workspace workflows in the SourceOS office suite.

## Scope

Reference suite:
- Docs
- Sheets
- Slides
- Drive
- Forms
- comments / suggestions / revisions
- workflow studio-style automations

The goal is cloud-workflow parity, not only file-format parity.

## Parity dimensions

- export/import fidelity
- collaboration fidelity
- Drive-like object and sharing fidelity
- workflow and automation fidelity
- AI task fidelity
- migration fidelity

## Docs

Required targets:
- import/export of common Docs-derived artifacts
- comments and suggestions model
- section rewrite / summarize / draft
- document Q&A grounded in workspace context
- export to ODT, DOCX, PDF

Known risk classes:
- comments/suggestions metadata loss across some export paths
- proprietary Workspace-only features without direct local analogue

## Sheets

Required targets:
- import/export of common Sheets-derived artifacts
- formula compatibility classification
- chart generation and explanation
- summary and anomaly surfacing
- export to ODS, XLSX, CSV where appropriate

Known risk classes:
- Apps Script / macros
- some Sheets-specific function families
- Drive metadata around revisions and sharing

## Slides

Required targets:
- import/export of common Slides-derived artifacts
- comments and speaker-note path
- slide summarization and generation
- export to ODP, PPTX, PDF

Known risk classes:
- Workspace-only media and theme behaviors
- comments/revision metadata loss on export

## Drive / Files

Required targets:
- document and folder discovery
- permission-aware search
- versions
- sharing model
- export/download path
- folder/workspace Q&A

## Workflow studio targets

Required targets:
- starters
- steps/actions
- approvals
- schedules
- office/document-centered automations

## AI task targets

Required targets:
- grounded drafting
- file-aware Q&A
- spreadsheet analysis
- deck summarization / generation
- workflow action suggestions

## Migration targets

Required targets:
- Google export inventory scan
- parity result classification
- script/macro classification
- remediation suggestions

## Scoring classes

- GREEN = safe parity
- YELLOW = acceptable with warnings
- ORANGE = manual review needed
- RED = unsupported / high-risk
- BLACK = blocked by policy or security
