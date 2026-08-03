"""self-query conformance — runnable with `python3 tests/conformance_test.py` (no pytest dep).

Teeth verified BOTH ways (ADR-0001 discipline), closing GAP #80:
  POSITIVE — NL queries with implied constraints extract the right {semantic_query, metadata_filter};
             the filter is a Qdrant-acceptable {must/must_not} shape that, applied to fixture points,
             returns the expected hits; the residual semantic query has the filter phrase stripped.
  NEGATIVE — a proposed filter over an UNDECLARED field or an UNSUPPORTED operator is REJECTED with
             the expected stable code (no silent full-scan); an unrecognised phrase passes through
             cleanly as semantic-only (no bogus filter).
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
sys.path.insert(0, PKG)
sys.path.insert(0, os.path.join(PKG, "fixtures"))

from self_query import (  # noqa: E402
    CORPUS_SCHEMA, MEMORYMESH_SCHEMA, FilterRejected, build_self_query, compile_filter,
)
from qdrant_fixture import apply_filter  # noqa: E402

_passed = 0
_failed = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global _passed, _failed
    if cond:
        _passed += 1
        print(f"  ok   {name}")
    else:
        _failed += 1
        print(f"  FAIL {name} :: {detail}")


def expect_reject(name: str, fn, code: str) -> None:
    try:
        fn()
        check(name, False, f"expected reject {code}, but it succeeded")
    except FilterRejected as e:
        check(name, e.code == code, f"expected {code}, got {e.code}")


def main() -> int:
    # --- POSITIVE: enum constraint extracted, filter Qdrant-shaped, executes -----------------------
    sq = build_self_query("find fact memories about coastal erosion")
    check("enum extracted → memory_class match:{value:fact}",
          sq.metadata_filter.get("must") == [{"key": "memory_class", "match": {"value": "fact"}}],
          str(sq.metadata_filter))
    check("residual semantic query strips the class word",
          "fact" not in sq.semantic_query.lower() and "erosion" in sq.semantic_query.lower(),
          sq.semantic_query)
    hits = apply_filter(sq.metadata_filter)
    check("fact filter executes → p1,p3", hits == ["p1", "p3"], str(hits))

    # --- POSITIVE: temporal 'after 2021' → range on created_at, executes ---------------------------
    sq = build_self_query("summary notes about erosion after 2021")
    must = {c["key"]: c for c in sq.metadata_filter.get("must", [])}
    check("temporal 'after 2021' → created_at range gte 2021-01-01",
          must.get("created_at", {}).get("range", {}).get("gte") == "2021-01-01", str(sq.metadata_filter))
    check("enum 'summary' also extracted alongside the range",
          any(c.get("match", {}).get("value") == "summary" for c in sq.metadata_filter["must"]),
          str(sq.metadata_filter))
    hits = apply_filter(sq.metadata_filter)
    check("summary+after-2021 executes → p4 only", hits == ["p4"], str(hits))

    # --- POSITIVE: 'in 2023' → half-open year range, executes --------------------------------------
    sq = build_self_query("what happened in 2023")
    hits = apply_filter(sq.metadata_filter)
    check("in-2023 executes → p3 only", hits == ["p3"], f"{sq.metadata_filter} -> {hits}")

    # --- POSITIVE: tags → membership ($in → match:any), executes -----------------------------------
    sq = build_self_query("notes tagged coastal")
    check("tag → tags match:{any:[coastal]}",
          {"key": "tags", "match": {"any": ["coastal"]}} in sq.metadata_filter.get("must", []),
          str(sq.metadata_filter))
    hits = apply_filter(sq.metadata_filter)
    check("tagged-coastal executes → p3 only", hits == ["p3"], str(hits))

    # --- POSITIVE: corpus schema — 'papers on X after 2020' → int year range ($gt) -----------------
    sq = build_self_query("papers on transformers after 2020", schema=CORPUS_SCHEMA)
    check("corpus 'after 2020' → year range gt 2020 (int)",
          sq.metadata_filter.get("must") == [{"key": "year", "range": {"gt": 2020}}],
          str(sq.metadata_filter))
    check("corpus residual keeps the topic", "transformers" in sq.semantic_query.lower(),
          sq.semantic_query)

    # --- POSITIVE: 'in domain X' → domain eq (corpus) ---------------------------------------------
    sq = build_self_query("papers in domain biology", schema=CORPUS_SCHEMA)
    check("'in domain biology' → domain match:{value:biology}",
          {"key": "domain", "match": {"value": "biology"}} in sq.metadata_filter.get("must", []),
          str(sq.metadata_filter))

    # --- POSITIVE: unrecognised phrasing → clean semantic-only passthrough (no bogus filter) -------
    sq = build_self_query("tell me something interesting about the ocean")
    check("no filter phrase → empty metadata_filter, full query preserved",
          sq.metadata_filter == {} and "ocean" in sq.semantic_query.lower(),
          str(sq.to_dict()))

    # --- POSITIVE: compile_filter direct — range merge + $in + $exists -----------------------------
    flt = compile_filter({"created_at": {"$gte": "2021-01-01", "$lt": "2024-01-01"},
                          "memory_class": {"$in": ["fact", "decision"]},
                          "user_id": {"$exists": True}})
    check("range operators merge into one range condition",
          {"key": "created_at", "range": {"gte": "2021-01-01", "lt": "2024-01-01"}} in flt["must"],
          str(flt))
    check("$in → match:any", {"key": "memory_class", "match": {"any": ["fact", "decision"]}} in flt["must"],
          str(flt))
    check("$exists:true → must_not is_empty",
          {"is_empty": {"key": "user_id"}} in flt.get("must_not", []), str(flt))
    hits = apply_filter(flt)
    check("compiled multi-op filter executes → p2,p3", hits == ["p2", "p3"], str(hits))

    # --- POSITIVE: $exists over an optional field (created_at missing on p5) ------------------------
    hits = apply_filter(compile_filter({"created_at": {"$exists": True}}))
    check("$exists created_at excludes p5 (no created_at)", "p5" not in hits and len(hits) == 4,
          str(hits))

    # --- NEGATIVE: undeclared field is rejected (fail-closed, no full-scan) -------------------------
    expect_reject("reject compile over undeclared field",
                  lambda: compile_filter({"password": {"$eq": "x"}}), "unknown-field")
    expect_reject("reject NL naming an undeclared field explicitly (ssn:123)",
                  lambda: build_self_query("find memories where ssn:12345"), "unknown-field")

    # --- NEGATIVE: unsupported operator rejected ---------------------------------------------------
    expect_reject("reject unsupported operator $regex",
                  lambda: compile_filter({"memory_class": {"$regex": ".*"}}), "unsupported-operator")

    # --- NEGATIVE: enum value not in declared set --------------------------------------------------
    expect_reject("reject out-of-enum value",
                  lambda: compile_filter({"memory_class": {"$eq": "banana"}}), "enum-value")

    # --- NEGATIVE: operand type mismatch (range on int field with a string) ------------------------
    expect_reject("reject int-range operand type mismatch",
                  lambda: compile_filter({"year": {"$gt": "twenty"}}, schema=CORPUS_SCHEMA),
                  "operand-type")
    expect_reject("reject $in with a non-list operand",
                  lambda: compile_filter({"tags": {"$in": "coastal"}}), "operand-type")

    # --- NEGATIVE: empty question ------------------------------------------------------------------
    expect_reject("reject empty question", lambda: build_self_query("   "), "empty")

    print(f"\n{_passed} passed, {_failed} failed")
    return 1 if _failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
