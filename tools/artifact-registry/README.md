# artifact-registry (MS-P6) — grade ladder + AC-01..12 registry

Closes the last two gaps of the Metadata Standards adoption (GAP-6, GAP-7).

## grade_ladder.py — evidence_grade ⟷ epistemic ceiling (GAP-6)
Reconciles the standard's 5 evidence grades with the workspace controller's 4 epistemic levels (WO-C):
`E1→Speculative · E2,E3→Derived · E4→Measured · E5→Proved` — an authoritative, **monotonic** map with
floor-grade round-trips and `grade_meets_ceiling()` for admitting records into a workspace.

## artifact_registry.py — AC-01..12 (GAP-7)
The artifact-class registry (standard §4): each class → `{name, source_formats, enrichments, zone_path}`.
`name` matches the metadata-record `artifact_class` enum; every `zone_path` is validated against the
canonical **WNZL** zone order (MS-P5). `enrichment_path()` / `zone_path()` route an artifact through its
parsers and zones (e.g. LegalFiling → …→Governed; FirmwareDump → Landing→Examination).

## Verify
`python3 tests/wo_msp6_test.py` → **17/17** — ladder correctness + monotonicity + floor round-trip +
meets-ceiling; all 12 classes with valid in-order zone paths; enrichment/zone routing; and cross-checks
that class names + grades match the metadata-record schema.
