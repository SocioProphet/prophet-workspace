"""Workspace epistemic ceiling + mount-authority change — the epistemic gap over the mount table (WO-C).

The mount table (A4-31 / #39: schemas/workspace-mount-table.schema.json) already models the mount (f*)
capability surface with WS-5 enforced (no self-grant, warrant required). It does NOT model the EPISTEMIC
dimension. WO-C adds exactly that, consuming the existing table — never rewriting it:

  1. workspace_ceiling(): the workspace's epistemic level = the MEET (min) over its mounted sections'
     levels, then CLAMPED to `Derived` for an external principal (STAR-1 / ADR-0001 AC-2). This is the
     S2-projection ceiling of ADR-0001 sec.4.
  2. authority_change(): diff two mount tables into the WorkspaceInterfaceCrossing.authorityChange enum
     (none | reduced | expanded | ambiguous) and classify the Layer — widening (expanded/ambiguous) is
     Layer 2 (review required, WS-5); narrowing/none is Layer 1 (free). This is the order relation in B.
  3. admit_publish(): a publish/answer may not exceed the workspace ceiling.

Levels match the ProofArtifact spine (WO-B): Speculative < Derived < Measured < Proved.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

LEVELS = ["Speculative", "Derived", "Measured", "Proved"]
_RANK = {name: i for i, name in enumerate(LEVELS)}
EXTERNAL_CEILING = "Derived"                 # STAR-1: nothing external above Derived
DEFAULT_ENTRY_LEVEL = "Derived"             # a mounted source with no declared classification


class CeilingError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


def _load(table: dict | str | Path) -> dict:
    if isinstance(table, (str, Path)):
        return json.loads(Path(table).read_text())
    return table


@dataclass
class Ceiling:
    level: str                       # the workspace epistemic ceiling (meet, then external clamp)
    meet: str                        # meet over entries, before the external clamp
    clamped_by_external: bool
    per_entry: dict                  # sourceId -> level used


def workspace_ceiling(table: dict | str | Path, *, external: bool,
                      source_levels: dict[str, str] | None = None) -> Ceiling:
    """Compute the workspace epistemic ceiling = meet over mounted sections, clamped for external
    principals. `source_levels` maps sourceId -> declared classification (from the source catalog);
    unmapped sources default to Derived."""
    spec = _load(table)["spec"]
    source_levels = source_levels or {}
    entries = spec["entries"]
    per_entry: dict[str, str] = {}
    meet_rank = _RANK["Proved"]                     # start at top; meet drives it down
    for e in entries:
        lvl = source_levels.get(e["sourceId"], DEFAULT_ENTRY_LEVEL)
        if lvl not in _RANK:
            raise CeilingError("level-unknown", f"unknown epistemic level {lvl!r} for {e['sourceId']}")
        per_entry[e["sourceId"]] = lvl
        meet_rank = min(meet_rank, _RANK[lvl])
    meet = LEVELS[meet_rank] if entries else "Speculative"
    clamped = external and _RANK[meet] > _RANK[EXTERNAL_CEILING]
    level = EXTERNAL_CEILING if clamped else meet
    return Ceiling(level=level, meet=meet, clamped_by_external=clamped, per_entry=per_entry)


def admit_publish(ceiling: Ceiling, publish_level: str) -> None:
    """A publish/answer may not claim a level above the workspace ceiling. Raises on violation."""
    if publish_level not in _RANK:
        raise CeilingError("level-unknown", f"unknown publish level {publish_level!r}")
    if _RANK[publish_level] > _RANK[ceiling.level]:
        raise CeilingError("above-ceiling",
                           f"publish level {publish_level} exceeds workspace ceiling {ceiling.level}")


# --- mount-authority change (the order relation in B) -------------------------------------------------

def _extent_relation(prev: str, new: str) -> str:
    """Order over hierarchical extent URIs: narrower | wider | same | incomparable."""
    if prev == new:
        return "same"
    if new.startswith(prev.rstrip("/") + "/"):
        return "wider"          # new extends prev's path -> broader scope
    if prev.startswith(new.rstrip("/") + "/"):
        return "narrower"
    return "incomparable"


def _entry_key(e: dict) -> tuple:
    return (e["sourceId"], e["surface"], tuple(sorted(e["capabilities"])))


@dataclass
class AuthorityChange:
    change: str          # WorkspaceInterfaceCrossing.authorityChange enum
    layer: int           # 1 = free (narrowing/none), 2 = review required (widening/ambiguous)
    review_required: bool
    added: list
    removed: list


def authority_change(prev_table: dict | str | Path, new_table: dict | str | Path) -> AuthorityChange:
    """Diff two mount tables into an authorityChange verdict + Layer (WS-5). Widening (more extent, or
    an added source/capability) is Layer 2; pure narrowing or no change is Layer 1."""
    pspec, nspec = _load(prev_table)["spec"], _load(new_table)["spec"]
    prev_entries = {e["sourceId"]: _entry_key(e) for e in pspec["entries"]}
    new_entries = {e["sourceId"]: _entry_key(e) for e in nspec["entries"]}

    added = [s for s in new_entries if s not in prev_entries]
    removed = [s for s in prev_entries if s not in new_entries]
    # capability widening on a retained source counts as an add
    cap_widened = [s for s in new_entries
                   if s in prev_entries and set(new_entries[s][2]) - set(prev_entries[s][2])]
    added_all = sorted(set(added) | set(cap_widened))

    ext = _extent_relation(pspec["declaredExtent"], nspec["declaredExtent"])

    if ext == "incomparable":
        change = "ambiguous"
    elif ext == "wider" or added_all:
        change = "expanded"
    elif ext == "narrower" or removed:
        change = "reduced"
    else:
        change = "none"

    widening = change in ("expanded", "ambiguous")
    return AuthorityChange(change=change, layer=2 if widening else 1,
                           review_required=widening, added=added_all, removed=sorted(removed))
