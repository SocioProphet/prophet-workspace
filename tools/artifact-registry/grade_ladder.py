"""Evidence-grade ⟷ epistemic-ceiling reconciliation (MS-P6, GAP-6).

The Metadata Standards classification block grades evidence on FIVE levels (E1..E5); the workspace
controller's epistemic ceiling (WO-C) has FOUR (Speculative < Derived < Measured < Proved). They are
near-isomorphic; this defines the authoritative, monotonic mapping so a metadata-record's evidence_grade
and a workspace's epistemic ceiling speak one ladder.

  E1 Speculative   (no source artifact)                         → Speculative
  E2 Claimed       (source cited, not verified)                 → Derived
  E3 Located       (source in corpus, not yet authenticated)    → Derived
  E4 Authenticated (hash verified, chain intact)                → Measured
  E5 Corroborated  (independently verified vs a second source)  → Proved

The map is order-preserving (monotonic): a higher evidence grade never maps to a lower epistemic level.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "workspace-controller"))
from epistemic_ceiling import LEVELS, _RANK  # noqa: E402  (WO-C is the epistemic-level authority)

EVIDENCE_GRADES = ["E1", "E2", "E3", "E4", "E5"]
_GRADE_RANK = {g: i for i, g in enumerate(EVIDENCE_GRADES)}

# authoritative grade → epistemic level
GRADE_TO_LEVEL = {"E1": "Speculative", "E2": "Derived", "E3": "Derived", "E4": "Measured", "E5": "Proved"}
# epistemic level → the MINIMUM (floor) evidence grade that reaches it
LEVEL_TO_FLOOR_GRADE = {"Speculative": "E1", "Derived": "E2", "Measured": "E4", "Proved": "E5"}


class LadderError(Exception):
    pass


def grade_to_level(grade: str) -> str:
    if grade not in GRADE_TO_LEVEL:
        raise LadderError(f"unknown evidence_grade {grade!r}")
    return GRADE_TO_LEVEL[grade]


def level_floor_grade(level: str) -> str:
    if level not in LEVEL_TO_FLOOR_GRADE:
        raise LadderError(f"unknown epistemic level {level!r}")
    return LEVEL_TO_FLOOR_GRADE[level]


def grade_meets_ceiling(grade: str, ceiling_level: str) -> bool:
    """Does an artifact of this evidence_grade satisfy a workspace's epistemic ceiling? (Its mapped
    level must be >= the ceiling in the shared ladder — used when admitting a record into a workspace.)"""
    return _RANK[grade_to_level(grade)] >= _RANK[ceiling_level]


def is_monotonic() -> bool:
    """The map preserves order: E1<=E2<=…<=E5 ⇒ epistemic ranks non-decreasing. Guards accidental edits."""
    ranks = [_RANK[GRADE_TO_LEVEL[g]] for g in EVIDENCE_GRADES]
    return all(ranks[i] <= ranks[i + 1] for i in range(len(ranks) - 1))


def check_consistency() -> list[str]:
    """Self-check the reconciliation (used by the conformance test + importable as a guard)."""
    errs = []
    if not is_monotonic():
        errs.append("grade→level map is not monotonic")
    for lvl, g in LEVEL_TO_FLOOR_GRADE.items():
        if GRADE_TO_LEVEL[g] != lvl:
            errs.append(f"floor grade {g} for {lvl} does not map back to {lvl}")
    if set(GRADE_TO_LEVEL.values()) - set(LEVELS):
        errs.append("grade map targets a level not in WO-C LEVELS")
    return errs
