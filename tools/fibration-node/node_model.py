"""Semantic-Fibration node model (WO-H of ADR-0001) — the per-node topology of knowing.

Each intelligent mesh node carries its own epistemic fiber over the shared hypergraph:
  - S3  = the shared graph (HellGraph) — semantic reality all nodes co-inhabit;
  - S1  = the node's fiber — its mounted cover + orientation (the mount table, WO-C);
  - S2  = the node's projected worldview — what it holds as knowledge, and at what epistemic level.

This module makes that operational, NOT metaphorical:
  - descent test per mounted section: does the node's LOCAL view glue with the SHARED (S3) view?
      glues            -> full, epistemic as declared (up to ceiling)
      degraded         -> read-only, epistemic = Speculative, the disagreement LOCALISED IN PLACE (WS-6)
      blocked          -> gate closed at this section and above (non-localisable obstruction)
  - fiber alignment: ontology (model) vs epistemology (observed). Converge -> resonance; diverge ->
    a misaligned fiber = a descent obstruction surfaced, never hidden.
  - FIB-9 decay: a section not refreshed within its window decays — epistemic level drops, and past a
    threshold falls to read-only.
  - "truth is what survives the loop": a claim is TRUE iff it keeps a valid ProofArtifact (WO-B) AND its
    section glues after descent + decay. Blocked/degraded/decayed-out claims do not survive.

Levels reuse WO-C (Speculative < Derived < Measured < Proved) so the whole continuum shares one vocabulary.
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "workspace-controller"))
from epistemic_ceiling import LEVELS, _RANK, EXTERNAL_CEILING  # noqa: E402  (WO-C vocabulary)


def _lower(level: str, floor: str = "Speculative") -> str:
    return LEVELS[max(_RANK[floor], _RANK[level] - 1)]


@dataclass
class Section:
    """A mounted section of the cover: the node's local value, the shared (S3) value, its declared
    epistemic level, the ids of overlapping sections, and how stale it is (in decay windows)."""
    id: str
    local_value: str
    shared_value: str
    declared_level: str = "Derived"
    overlaps: list = field(default_factory=list)         # ids of overlapping sections in the cover
    windows_since_refresh: float = 0.0                    # FIB-9: age in decay windows


@dataclass
class SectionVerdict:
    id: str
    verdict: str            # glues | degraded | blocked
    mode: str               # full | read-only | blocked
    level: str              # epistemic level after descent + decay
    obstruction: dict | None  # localised disagreement, surfaced in place (WS-6)


def _decay(level: str, windows: float, *, degrade_after: float = 2.0) -> tuple[str, bool]:
    """FIB-9: each full window past the first lowers the level a step; past `degrade_after`, read-only."""
    steps = int(windows)
    lvl = level
    for _ in range(steps):
        lvl = _lower(lvl)
    return lvl, windows >= degrade_after


def descend_section(sec: Section, others: dict) -> SectionVerdict:
    """Descent test for one section against the shared graph, with FIB-9 decay applied."""
    decayed_level, decayed_readonly = _decay(sec.declared_level, sec.windows_since_refresh)

    if sec.local_value == sec.shared_value:
        # glues — but decay may still have lowered the level / forced read-only
        return SectionVerdict(sec.id, "glues", "read-only" if decayed_readonly else "full",
                              decayed_level, obstruction=None)

    # disagreement: localisable iff the overlapping sections still glue (conflict confined here)
    conflicting_overlaps = [o for o in sec.overlaps
                            if o in others and others[o].local_value != others[o].shared_value]
    obstruction = {"section": sec.id, "local": sec.local_value, "shared": sec.shared_value,
                   "conflicting_overlaps": conflicting_overlaps}
    if conflicting_overlaps:
        # non-localisable: the disagreement spans the cover -> gate closed here and above
        return SectionVerdict(sec.id, "blocked", "blocked", "Speculative", obstruction)
    # localisable: degrade read-only at Speculative, disagreement surfaced IN PLACE
    return SectionVerdict(sec.id, "degraded", "read-only", "Speculative", obstruction)


@dataclass
class Projection:
    """The node's S2 worldview: per-section verdicts + the workspace-level ceiling (meet), and whether
    the extent is gated by any blocking obstruction."""
    sections: dict                # id -> SectionVerdict
    s2_ceiling: str               # meet over section levels (clamped for external principals)
    gated: bool                   # any section blocked -> the extent above is closed
    obstructions: list            # surfaced disagreements (degraded + blocked)


def project_worldview(sections: list[Section], *, external: bool = False) -> Projection:
    """Project S1 (the cover) into S2 (the worldview) via descent + decay. External nodes are clamped
    to the Derived ceiling (STAR-1)."""
    others = {s.id: s for s in sections}
    verdicts = {s.id: descend_section(s, others) for s in sections}
    meet_rank = _RANK["Proved"]
    for v in verdicts.values():
        meet_rank = min(meet_rank, _RANK[v.level])
    meet = LEVELS[meet_rank] if verdicts else "Speculative"
    if external and _RANK[meet] > _RANK[EXTERNAL_CEILING]:
        meet = EXTERNAL_CEILING
    gated = any(v.verdict == "blocked" for v in verdicts.values())
    obstructions = [v.obstruction for v in verdicts.values() if v.obstruction is not None]
    return Projection(sections=verdicts, s2_ceiling=meet, gated=gated, obstructions=obstructions)


def fiber_alignment(ontology_view: dict, epistemology_view: dict) -> dict:
    """Ontology (model's expected values) vs epistemology (observed values) over the same keys.
    Converge -> resonance; diverge -> misaligned fiber (a descent obstruction at the fiber level)."""
    keys = set(ontology_view) | set(epistemology_view)
    divergences = [k for k in keys if ontology_view.get(k) != epistemology_view.get(k)]
    return {"aligned": not divergences,
            "state": "resonance" if not divergences else "misaligned",
            "divergences": sorted(divergences)}


def survives_loop(section_verdict: SectionVerdict, *, has_proof_artifact: bool) -> bool:
    """Truth is what survives the loop: a claim survives iff its section GLUES after descent+decay AND it
    carries a valid ProofArtifact (WO-B). Degraded, blocked, or unreceipted claims do not survive."""
    return section_verdict.verdict == "glues" and has_proof_artifact
