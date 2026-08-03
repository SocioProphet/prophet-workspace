"""TemporalRetrievalFilter conformance — `python3 tests/conformance_test.py` (no pytest dep).

Teeth both ways, and proof that the filter is genuinely UNIFORM (not regis-only):

  1. regis fixture: John-Smith -> Jenna-Brown supersession resolves to the newest; high-recall
     surfaces BOTH, the superseded John-Smith fact is excluded, Jenna Brown is authoritative.
  2. a candidate set with NO temporal fields passes through UNCHANGED (identity + order).
  3. a malformed temporal record (superseded_at < valid_from) is REJECTED; likewise
     valid_to < valid_from, and supersession markers with no valid_from to order against.
  4. it composes with a GENERIC ranked list under a NON-regis field map (subject/predicate/
     effective_from/...): most-recent wins, the old fact is suppressed, an unrelated
     non-temporal chunk passes through in its original rank position.
  5. consume-not-fork: when regis-entity-graph is locatable, this filter's `resolve()` equals
     regis#20's shipped `temporal_retrieve()` on the regis fixture (oracle-pinned). It never
     re-derives a rival invariant.

A filter that silently keeps a superseded fact, drops an opaque candidate, reorders the ranked
list, or disagrees with the regis oracle fails this suite.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG = HERE.parent
FIXTURES = HERE / "fixtures"
sys.path.insert(0, str(PKG))

from temporal_retrieval_filter import (  # noqa: E402
    DEFAULT_FIELD_MAP,
    FieldMap,
    TemporalRecordError,
    TemporalRetrievalFilter,
    is_superseded,
)

_passed = _failed = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global _passed, _failed
    if cond:
        _passed += 1
        print(f"  ok   {name}")
    else:
        _failed += 1
        print(f"  FAIL {name} :: {detail}")


def load(path: Path):
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


# --------------------------------------------------------------------------- #
# 1. regis supersession — newest wins (default field map == regis vocabulary)
# --------------------------------------------------------------------------- #
def test_regis_supersession() -> None:
    facts = load(FIXTURES / "regis_ceo_supersession.facts.json")
    filt = TemporalRetrievalFilter()  # DEFAULT_FIELD_MAP is regis vocabulary
    result = filt.apply(facts)

    # High-recall: both facts were in the input (so exclusion is real suppression).
    input_values = {f["value"] for f in facts}
    check("high-recall input carries both facts", {"John Smith", "Jenna Brown"} <= input_values,
          f"got {input_values}")

    kept_values = {f["value"] for f in result.kept}
    check("superseded John-Smith excluded from kept", "John Smith" not in kept_values,
          f"kept={kept_values}")
    check("current Jenna-Brown survives", "Jenna Brown" in kept_values, f"kept={kept_values}")

    key = ("urn:regis:entity:org:abc-corp", "HAS_CEO")
    auth = result.authoritative.get(key)
    check("authoritative CEO is Jenna Brown (max valid_from)",
          auth is not None and auth["value"] == "Jenna Brown",
          f"got {auth}")
    reasons = {s["reason"] for s in result.suppressed}
    check("John-Smith suppressed for reason 'superseded'", reasons == {"superseded"}, f"got {reasons}")


# --------------------------------------------------------------------------- #
# 2. no temporal fields -> pass through unchanged
# --------------------------------------------------------------------------- #
def test_pass_through() -> None:
    ranked = [
        {"doc_id": "d1", "text": "alpha", "score": 0.9},
        {"doc_id": "d2", "text": "beta", "score": 0.7},
        {"doc_id": "d3", "text": "gamma", "score": 0.5},
    ]
    result = TemporalRetrievalFilter().apply(ranked)
    check("opaque ranked list passes through unchanged (identity + order)",
          result.kept == ranked and all(a is b for a, b in zip(result.kept, ranked)),
          f"kept={result.kept}")
    check("no opaque candidate is suppressed", result.suppressed == [], f"got {result.suppressed}")


# --------------------------------------------------------------------------- #
# 3. malformed temporal records are rejected (fail-closed)
# --------------------------------------------------------------------------- #
def test_malformed_rejected() -> None:
    time_travel = [{
        "entity": "org:abc", "relation": "HAS_CEO", "value": "John Smith",
        "valid_from": "2019-06-01T00:00:00Z", "valid_to": "2025-01-15T00:00:00Z",
        "superseded_by": "f:jenna", "superseded_at": "2018-01-01T00:00:00Z",  # < valid_from
    }]
    try:
        TemporalRetrievalFilter().apply(time_travel)
        check("superseded_at < valid_from rejected", False, "wrongly accepted")
    except TemporalRecordError:
        check("superseded_at < valid_from rejected", True)

    inverted = [{
        "entity": "org:abc", "relation": "HAS_CEO", "value": "John Smith",
        "valid_from": "2025-01-15T00:00:00Z", "valid_to": "2019-06-01T00:00:00Z",  # < valid_from
    }]
    try:
        TemporalRetrievalFilter().apply(inverted)
        check("valid_to < valid_from rejected", False, "wrongly accepted")
    except TemporalRecordError:
        check("valid_to < valid_from rejected", True)

    no_vf = [{
        "entity": "org:abc", "relation": "HAS_CEO", "value": "John Smith",
        "superseded_by": "f:jenna",  # supersession marker but nothing to order against
    }]
    try:
        TemporalRetrievalFilter().apply(no_vf)
        check("supersession marker without valid_from rejected", False, "wrongly accepted")
    except TemporalRecordError:
        check("supersession marker without valid_from rejected", True)


# --------------------------------------------------------------------------- #
# 4. composes with a GENERIC ranked list under a NON-regis field map
# --------------------------------------------------------------------------- #
def test_generic_ranked_list() -> None:
    fmap = FieldMap(
        entity="subject", relation="predicate",
        valid_from="effective_from", valid_to="expired_at",
        superseded_by="replaced_by", superseded_at="replaced_at",
    )
    # A realistic mixed RAG re-rank: an outdated fact ranked ABOVE its replacement, plus an
    # unrelated non-temporal passage in the middle, plus a second independent (subject,predicate).
    ranked = [
        {"subject": "product:widget", "predicate": "price", "answer": "$9",
         "effective_from": "2021-01-01T00:00:00Z", "expired_at": "2024-01-01T00:00:00Z",
         "replaced_by": "f:widget-price-2024", "replaced_at": "2024-01-01T00:00:00Z"},
        {"doc": "glossary passage about pricing", "score": 0.6},           # opaque, mid-rank
        {"subject": "product:widget", "predicate": "price", "answer": "$12",
         "effective_from": "2024-01-01T00:00:00Z"},                        # the current fact
        {"subject": "product:widget", "predicate": "color", "answer": "blue",
         "effective_from": "2020-01-01T00:00:00Z"},                        # different relation
    ]
    result = TemporalRetrievalFilter(fmap).apply(ranked)
    answers = [r.get("answer") for r in result.kept]
    check("generic: outdated $9 suppressed", "$9" not in answers, f"kept answers={answers}")
    check("generic: current $12 wins", "$12" in answers, f"kept answers={answers}")
    check("generic: unrelated color fact untouched", "blue" in answers, f"kept answers={answers}")
    check("generic: non-temporal passage passes through in place",
          result.kept[0].get("doc") == "glossary passage about pricing",
          f"kept[0]={result.kept[0]}")
    check("generic: kept ranking order preserved",
          answers == ["$12", "blue"] or result.kept[0].get("doc") is not None,
          f"kept={[list(r.keys()) for r in result.kept]}")
    # exact expected surviving order: [passage(opaque, rank1), $12(rank2), blue(rank3)]
    check("generic: exact surviving order",
          [r.get("doc") or r.get("answer") for r in result.kept]
          == ["glossary passage about pricing", "$12", "blue"],
          f"kept={[r.get('doc') or r.get('answer') for r in result.kept]}")


# --------------------------------------------------------------------------- #
# 5. consume-not-fork: agree with regis#20's shipped temporal_retrieve (oracle)
# --------------------------------------------------------------------------- #
def _locate_regis_oracle():
    """Best-effort locate regis-entity-graph's shipped validator for oracle cross-check."""
    candidates = []
    env = os.environ.get("REGIS_ENTITY_GRAPH")
    if env:
        candidates.append(Path(env) / "tools" / "validate_temporal_supersession.py")
    # sibling checkout in the same dev root (…/dev/regis-entity-graph)
    candidates.append(PKG.parents[2] / "regis-entity-graph" / "tools" / "validate_temporal_supersession.py")
    candidates.append(Path.home() / "dev" / "regis-entity-graph" / "tools" / "validate_temporal_supersession.py")
    for path in candidates:
        if path.exists():
            return path
    return None


def test_oracle_agreement() -> None:
    oracle_path = _locate_regis_oracle()
    if oracle_path is None:
        print("  skip regis oracle cross-check (regis-entity-graph not locatable; "
              "set REGIS_ENTITY_GRAPH). Vendored-fixture teeth above still apply.")
        return
    spec = importlib.util.spec_from_file_location("regis_temporal_oracle", oracle_path)
    oracle = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(oracle)  # type: ignore[union-attr]

    facts = load(FIXTURES / "regis_ceo_supersession.facts.json")
    entity, relation = "urn:regis:entity:org:abc-corp", "HAS_CEO"
    theirs = oracle.temporal_retrieve(facts, entity, relation)
    ours = TemporalRetrievalFilter().resolve(facts, entity, relation)

    check("oracle: same authoritative fact",
          theirs["authoritative"]["fact_id"] == ours["authoritative"]["fact_id"],
          f"theirs={theirs['authoritative']['fact_id']} ours={ours['authoritative']['fact_id']}")
    check("oracle: same suppressed set",
          {f["fact_id"] for f in theirs["suppressed"]} == {f["fact_id"] for f in ours["suppressed"]},
          "suppressed sets differ")
    check("oracle: same surviving set",
          {f["fact_id"] for f in theirs["surviving"]} == {f["fact_id"] for f in ours["surviving"]},
          "surviving sets differ")
    check("oracle: is_superseded agrees per fact",
          all(oracle.is_superseded(f) == is_superseded(f, DEFAULT_FIELD_MAP) for f in facts),
          "is_superseded disagreement")


def main() -> int:
    print("TemporalRetrievalFilter conformance (GAP-2 / pw#84)")
    test_regis_supersession()
    test_pass_through()
    test_malformed_rejected()
    test_generic_ranked_list()
    test_oracle_agreement()
    print(f"\n{_passed} passed, {_failed} failed")
    return 1 if _failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
