# Microsoft Office Parity Matrix

This matrix defines the product-level parity targets for Microsoft Office workflows in the SourceOS office suite.

## Scope

Reference suite:
- Word
- Excel
- PowerPoint
- OneDrive / SharePoint-style document workflows

The goal is not bit-for-bit UI cloning. The goal is measurable workflow parity with explicit fidelity classes and declared exceptions.

## Parity dimensions

- file fidelity
- workflow fidelity
- collaboration fidelity
- admin/policy fidelity
- AI task fidelity
- migration fidelity

## Writer / Word

Required targets:
- open/edit/save DOCX
- comments
- tracked changes or equivalent review path
- headers/footers
- tables
- styles and headings
- export to PDF and ODT
- summary / rewrite / draft actions with receipts

Known risk classes:
- advanced embedded objects
- macros / VBA
- proprietary fonts
- complex pagination edge cases

## Calc / Excel

Required targets:
- open/edit/save XLSX
- formula compatibility classification
- charts
- pivot-like summaries
- filters and sorting
- export to PDF and ODS
- formula explanation and generation with receipts

Known risk classes:
- VBA macros
- external data connections
- unsupported or partially compatible formula families

## Impress / PowerPoint

Required targets:
- open/edit/save PPTX
- speaker notes
- themes / masters parity target
- export to PDF and ODP
- summary / slide generation / speaker-note assistance

Known risk classes:
- advanced animations
- embedded media edge cases
- proprietary theme/font combinations

## Cloud workflow targets

Required targets:
- browser open/edit/save through cloud editor
- versions
- locks and conflict handling
- preview/export
- comments and suggestions path

## AI task targets

Required targets:
- summarize document / workbook / deck
- rewrite selection / section
- explain formula
- propose chart
- generate slide outline
- draft follow-up mail from office context

## Migration targets

Required targets:
- corpus scan
- macro detection
- font risk report
- parity result classification
- remediation actions

## Scoring classes

- GREEN = safe parity
- YELLOW = acceptable with warnings
- ORANGE = manual review needed
- RED = unsupported / high-risk
- BLACK = blocked by policy or security
