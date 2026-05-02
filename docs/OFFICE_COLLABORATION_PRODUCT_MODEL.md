# Office Collaboration Product Model

This document defines the product-level collaboration model for the SourceOS office and workspace suite.

The goal is to make comments, suggestions, and review state first-class product objects rather than side notes hidden inside file-format compatibility work.

## Core product objects

### OfficeCollaborationThread

Represents a user-visible collaboration thread anchored to an office artifact or semantic unit.

Examples:
- comment thread on a paragraph
- review thread on a slide
- discussion thread on a spreadsheet cell range

Key concerns:
- thread type
- anchor target
- participants
- open/resolved state
- relation to versions and receipts

### OfficeSuggestion

Represents a proposed document change that can be reviewed, accepted, or rejected.

Examples:
- suggested wording change
- suggested table edit
- suggested speaker-note revision

Key concerns:
- target artifact and anchor
- before/after representation
- proposer
- approval state
- version linkage

### OfficeReviewState

Represents the current collaboration/review posture for an artifact or thread.

Examples:
- open review
- resolved comment thread
- accepted suggestion
- rejected suggestion

Key concerns:
- current status
- actor who changed status
- timestamp
- related version

## Product rules

1. Collaboration objects must be separate product objects, not just hidden editor metadata.
2. Collaboration state must be tied to office artifacts and versions.
3. Comments and suggestions must remain permission-aware and audit-friendly.
4. Agentic actions that create or modify collaboration state must produce evidence/receipt links.

## Cross-repo mapping

- `prophet-workspace` owns the product semantics and object model.
- `prophet-platform` owns runtime records, service seams, and storage/execution behavior.
- `source-os` owns local/cloud handoff and installed-shell affordances.
