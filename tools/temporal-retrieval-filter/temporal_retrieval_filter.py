"""TemporalRetrievalFilter — the UNIFORM temporal-correctness contract for the estate (GAP-2).

ADR-0002 §8 GAP-2 (pw#84, pw#76 item 1). regis-entity-graph#20 shipped the temporal
fact-supersession + `temporal_retrieve()` filter (high-recall -> suppress superseded ->
max-valid_from wins), but scoped to the regis *search* plane: its logic is welded to the
`regis.search.temporal_fact.v0.1` schema (const `schema_version`, regis field names, regis
provenance). ADR-0002 L1-T wants the SAME invariant applied uniformly across retrieval
surfaces (RAG router, memory-mesh, sherlock search) — not only the one that shipped.

This module LIFTS regis#20's invariant into a schema-agnostic core so any ranked candidate
set carrying `(entity, relation, valid_from, superseded_by?/superseded_at?)` — under whatever
field names that surface uses — gets outdated-fact suppression and most-recent-wins.

Consume-not-fork. This does NOT re-derive a rival invariant: the estate-canonical reference
is regis#20's `temporal_retrieve`, and this module's `resolve()` returns the identical trace
shape and, on regis facts, identical results (pinned as an oracle in the conformance suite).
The `DEFAULT_FIELD_MAP` deliberately uses regis vocabulary so a regis fact flows through the
default filter unchanged. Follow-up issues track regis#20 delegating to this shared core so
the invariant eventually has exactly one physical home, and per-surface wiring (RAG router,
memory-mesh).

The temporal invariants enforced here are the ones JSON Schema cannot express on its own:
mandatory `valid_from` (an untimestamped fact cannot be temporally ordered), `valid_to >=
valid_from`, and `superseded_at >= valid_from` (a fact cannot be retired before it began).

This filter is a *retrieval-plane* projection: it NEVER claims canonical truth. Canonical
supersession is owned by the ACR decision ledger / epistemic-edge promotion. Suppressing a
candidate here means "do not surface as the current answer", not "this is false".

Stdlib-only, matching the sibling continuum modules so `python3 tests/...` is an immediate
proof path with no third-party runtime dependency.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Mapping, Optional


class TemporalRecordError(ValueError):
    """A candidate carries temporal fields that violate a temporal invariant.

    Raised for malformed temporal records (superseded_at < valid_from, valid_to < valid_from,
    or supersession markers with no valid_from to order against). Fail-closed: a malformed
    temporal record is rejected, never silently kept.
    """


# --------------------------------------------------------------------------- #
# Field mapping — the decoupling from any one surface's schema.
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class FieldMap:
    """Names of the temporal fields on a candidate for a given retrieval surface.

    Different surfaces name the same concepts differently (a RAG chunk may carry
    ``subject``/``predicate``/``effective_from``; memory-mesh may carry ``key``/``ts``).
    A ``FieldMap`` lets the one filter read them all. Defaults are the regis vocabulary
    (regis#20), so regis facts feed the default filter with no mapping.
    """

    entity: str = "entity"
    relation: str = "relation"
    valid_from: str = "valid_from"
    valid_to: str = "valid_to"
    superseded_by: str = "superseded_by"
    superseded_at: str = "superseded_at"

    @property
    def _temporal_keys(self) -> tuple[str, ...]:
        return (self.valid_from, self.valid_to, self.superseded_by, self.superseded_at)


DEFAULT_FIELD_MAP = FieldMap()


def _get(record: Any, key: str) -> Any:
    """Read ``key`` from a candidate, supporting both mappings and attribute objects."""
    if isinstance(record, Mapping):
        return record.get(key)
    return getattr(record, key, None)


def parse_instant(value: Any, field_name: str) -> datetime:
    """Parse an RFC3339 / ISO-8601 date-time (``Z`` accepted). Raises on anything else."""
    if not (isinstance(value, str) and value):
        raise TemporalRecordError(f"{field_name} must be a non-empty RFC3339 date-time string")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise TemporalRecordError(f"{field_name} is not a valid date-time: {value!r} ({exc})")


# --------------------------------------------------------------------------- #
# Predicates over a single candidate.
# --------------------------------------------------------------------------- #
def has_temporal_fields(record: Any, fmap: FieldMap = DEFAULT_FIELD_MAP) -> bool:
    """True if the candidate carries ANY temporal field (so it participates in filtering).

    A candidate with none of them is temporally opaque and passes through unchanged.
    """
    return any(_get(record, k) is not None for k in fmap._temporal_keys)


def is_superseded(record: Any, fmap: FieldMap = DEFAULT_FIELD_MAP) -> bool:
    """A candidate is marked superseded when it carries a supersession pointer or instant.

    Identical semantics to regis#20's ``is_superseded``, read through the field map.
    """
    return _get(record, fmap.superseded_by) is not None or _get(record, fmap.superseded_at) is not None


def validate_temporal(record: Any, fmap: FieldMap = DEFAULT_FIELD_MAP) -> None:
    """Enforce the temporal invariants on a candidate that carries temporal fields.

    No-op for a temporally-opaque candidate (pass-through). For a temporal candidate,
    ``valid_from`` is mandatory and the ordering invariants are enforced. Raises
    ``TemporalRecordError`` on any violation (fail-closed).
    """
    if not has_temporal_fields(record, fmap):
        return

    vf_raw = _get(record, fmap.valid_from)
    if vf_raw is None:
        raise TemporalRecordError(
            f"candidate carries temporal fields but no {fmap.valid_from}; "
            "an untimestamped fact cannot be temporally ordered"
        )
    valid_from = parse_instant(vf_raw, fmap.valid_from)

    vt_raw = _get(record, fmap.valid_to)
    if vt_raw is not None:
        if parse_instant(vt_raw, fmap.valid_to) < valid_from:
            raise TemporalRecordError(
                f"{fmap.valid_to} ({vt_raw}) must be >= {fmap.valid_from} ({vf_raw})"
            )

    sa_raw = _get(record, fmap.superseded_at)
    if sa_raw is not None:
        if parse_instant(sa_raw, fmap.superseded_at) < valid_from:
            raise TemporalRecordError(
                f"{fmap.superseded_at} ({sa_raw}) must be >= {fmap.valid_from} ({vf_raw}) "
                "(a fact cannot be retired before it began)"
            )


# --------------------------------------------------------------------------- #
# Result of filtering a ranked candidate set.
# --------------------------------------------------------------------------- #
@dataclass
class FilterResult:
    """Outcome of applying the filter to a ranked candidate set.

    ``kept`` preserves the input ranking order (this is a filter over a ranked list): a
    surviving authoritative candidate keeps its original position; temporally-opaque
    candidates pass through in place. ``suppressed`` records each dropped candidate with a
    reason (``superseded`` | ``shadowed-by-newer``). ``authoritative`` maps each
    ``(entity, relation)`` key to its winning candidate.
    """

    kept: list[Any] = field(default_factory=list)
    suppressed: list[dict[str, Any]] = field(default_factory=list)
    authoritative: dict[tuple[str, str], Any] = field(default_factory=dict)


# --------------------------------------------------------------------------- #
# The filter.
# --------------------------------------------------------------------------- #
class TemporalRetrievalFilter:
    """Uniform temporal-correctness filter over any ranked candidate set.

    high-recall (the caller's ranked list) -> suppress superseded -> most-recent (max
    ``valid_from``) survivor per ``(entity, relation)`` wins. Candidates without temporal
    fields pass through unchanged. Malformed temporal records are rejected.
    """

    def __init__(self, field_map: FieldMap = DEFAULT_FIELD_MAP) -> None:
        self.fmap = field_map

    # -- helpers ---------------------------------------------------------- #
    def _key(self, record: Any) -> tuple[str, str]:
        return (str(_get(record, self.fmap.entity)), str(_get(record, self.fmap.relation)))

    def _valid_from(self, record: Any) -> datetime:
        return parse_instant(_get(record, self.fmap.valid_from), self.fmap.valid_from)

    # -- primary API ------------------------------------------------------ #
    def apply(self, candidates: list[Any]) -> FilterResult:
        """Filter a ranked candidate set. Validates then suppresses; see class docstring.

        Raises ``TemporalRecordError`` (fail-closed) if any candidate carries a malformed
        temporal record.
        """
        # Validate every candidate up front — a malformed temporal record fails the whole
        # pass rather than being silently dropped.
        for record in candidates:
            validate_temporal(record, self.fmap)

        # Partition and index the temporal candidates by supersession key, preserving the
        # first-seen (highest-ranked) index for stable tie-breaking.
        groups: dict[tuple[str, str], list[tuple[int, Any]]] = {}
        temporal_ids: set[int] = set()
        for idx, record in enumerate(candidates):
            if has_temporal_fields(record, self.fmap):
                temporal_ids.add(idx)
                groups.setdefault(self._key(record), []).append((idx, record))

        result = FilterResult()
        winners: set[int] = set()

        for key, members in groups.items():
            survivors = [(i, r) for (i, r) in members if not is_superseded(r, self.fmap)]
            for i, r in members:
                if is_superseded(r, self.fmap):
                    result.suppressed.append({"key": key, "reason": "superseded", "candidate": r})
            if not survivors:
                continue
            # max valid_from wins; ties resolved by earliest (highest) rank position.
            win_idx, win_rec = max(survivors, key=lambda ir: (self._valid_from(ir[1]), -ir[0]))
            winners.add(win_idx)
            result.authoritative[key] = win_rec
            for i, r in survivors:
                if i != win_idx:
                    result.suppressed.append({"key": key, "reason": "shadowed-by-newer", "candidate": r})

        # Rebuild the ranked list: opaque candidates in place, temporal winners in place.
        for idx, record in enumerate(candidates):
            if idx not in temporal_ids or idx in winners:
                result.kept.append(record)

        return result

    def filter(self, candidates: list[Any]) -> list[Any]:
        """Convenience: return only the surviving ranked list (``apply(...).kept``)."""
        return self.apply(candidates).kept

    def resolve(self, candidates: list[Any], entity: str, relation: str) -> dict[str, Any]:
        """Single-key trace, shape-compatible with regis#20's ``temporal_retrieve``.

        Returns ``{candidates, suppressed, surviving, authoritative}`` for one
        ``(entity, relation)`` — the estate-canonical trace shape, generalized to any field
        map. On regis facts with the default map this equals regis#20's output (oracle-pinned
        in the conformance suite): the consume-not-fork guarantee.
        """
        for record in candidates:
            validate_temporal(record, self.fmap)
        matched = [
            r for r in candidates
            if _get(r, self.fmap.entity) == entity and _get(r, self.fmap.relation) == relation
        ]
        suppressed = [r for r in matched if is_superseded(r, self.fmap)]
        surviving = [r for r in matched if not is_superseded(r, self.fmap)]
        authoritative: Optional[Any] = None
        if surviving:
            authoritative = max(surviving, key=self._valid_from)
        return {
            "candidates": matched,
            "suppressed": suppressed,
            "surviving": surviving,
            "authoritative": authoritative,
        }


def filter_candidates(
    candidates: list[Any], field_map: FieldMap = DEFAULT_FIELD_MAP
) -> list[Any]:
    """Module-level convenience for the common case: apply the default (or given) filter."""
    return TemporalRetrievalFilter(field_map).filter(candidates)
