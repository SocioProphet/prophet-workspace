"""WO-A conformance suite — runnable with `python3 tests/conformance_test.py` (no pytest dep).

Teeth verified BOTH ways (ADR-0001 discipline):
  - valid safe-subset queries return the CORRECT traversal rows against the CSKG fixture, and
  - every dangerous/out-of-subset query is REJECTED with the expected stable reason code, at the
    gateway AND (independently) at Sentinel.
"""
from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
sys.path.insert(0, PKG)  # import the gateway package modules by bare name

from adapter import InMemoryFixtureAdapter, TruthValue  # noqa: E402
from cypher_subset import HOP_CAP, LIMIT_CAP, CypherRejected, ParsedQuery  # noqa: E402
from gateway import SentinelDenied, query_cypher, sentinel_check  # noqa: E402

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


def load_adapter() -> InMemoryFixtureAdapter:
    a = InMemoryFixtureAdapter()
    with open(os.path.join(PKG, "fixtures", "cskg_mini.json")) as f:
        a.load_cskg(json.load(f)["triples"])
    return a


def expect_rejected(name: str, query: str, code: str, params=None) -> None:
    try:
        query_cypher(query, params or {}, load_adapter())
        check(name, False, f"expected rejection {code}, but query succeeded")
    except (CypherRejected, SentinelDenied) as e:
        check(name, e.code == code, f"expected {code}, got {e.code}")


def rows_forms(res) -> set[str]:
    key = next(k for k in res.rows[0].keys() if not k.startswith("_")) if res.rows else None
    return {r[key] for r in res.rows} if key else set()


def main() -> int:
    a = load_adapter()

    # --- valid queries return correct traversals (teeth: positive) ---
    r1 = query_cypher(
        "MATCH (h:Concept {form:$lemma})-[:CSKG*1..2]->(t) RETURN t.form LIMIT 25",
        {"lemma": "rain"}, a)
    check("2-hop any-relation from rain", rows_forms(r1) == {"weather", "flood", "phenomenon", "damage"},
          f"got {rows_forms(r1)}")

    r2 = query_cypher(
        'MATCH (h:Concept {form:"rain"})-[:CSKG*1..2 {relation:"IsA"}]->(t) RETURN t.form LIMIT 25',
        {}, a)
    check("2-hop IsA-only from rain", rows_forms(r2) == {"weather", "phenomenon"}, f"got {rows_forms(r2)}")

    r3 = query_cypher(
        'MATCH (h:Concept {form:"rain"})-[:CSKG*1..1]->(t) RETURN t.form LIMIT 25', {}, a)
    check("1-hop from rain", rows_forms(r3) == {"weather", "flood"}, f"got {rows_forms(r3)}")

    r4 = query_cypher(
        'MATCH (h:Concept {form:"rain"})-[:CSKG*1..2]->(t) RETURN t.form LIMIT 1', {}, a)
    check("LIMIT clamps row count", r4.row_count == 1, f"got {r4.row_count}")

    r5 = query_cypher(
        'MATCH (h:Concept {form:"dog"})-[:CSKG*1..2 {relation:"IsA"}]->(t) RETURN t.form LIMIT 25', {}, a)
    check("IsA chain dog->animal->organism", rows_forms(r5) == {"animal", "organism"}, f"got {rows_forms(r5)}")

    check("plan is emitted", bool(r1.plan) and any("expand" in p for p in r1.plan), f"plan={r1.plan}")
    check("truth composes along path (damage < weather)",
          next(rw for rw in r1.rows if rw.get("t.form") == "damage")["_truth"]["confidence"]
          < next(rw for rw in r1.rows if rw.get("t.form") == "weather")["_truth"]["confidence"])

    # --- dangerous / out-of-subset queries are rejected (teeth: negative) ---
    expect_rejected("reject CREATE (mutation)",
                    'CREATE (n:Concept {form:"x"}) RETURN n.form LIMIT 1', "mutation-create")
    expect_rejected("reject DELETE (mutation)",
                    'MATCH (h:Concept {form:"rain"})-[:CSKG*1..1]->(t) DELETE t RETURN t.form LIMIT 1',
                    "mutation-delete")
    expect_rejected("reject CALL (procedure)",
                    'CALL db.labels() YIELD label RETURN label LIMIT 1', "procedure-call")
    expect_rejected("reject WHERE (unsupported)",
                    'MATCH (h:Concept {form:"rain"})-[:CSKG*1..1]->(t) WHERE t.form="flood" RETURN t.form LIMIT 1',
                    "where-unsupported")
    expect_rejected("reject unbounded hops",
                    'MATCH (h:Concept {form:"rain"})-[:CSKG*]->(t) RETURN t.form LIMIT 25', "unbounded-hops")
    expect_rejected("reject hop over cap",
                    'MATCH (h:Concept {form:"rain"})-[:CSKG*1..5]->(t) RETURN t.form LIMIT 25', "hop-cap")
    expect_rejected("reject missing LIMIT",
                    'MATCH (h:Concept {form:"rain"})-[:CSKG*1..2]->(t) RETURN t.form', "limit-required")
    expect_rejected("reject LIMIT over cap",
                    'MATCH (h:Concept {form:"rain"})-[:CSKG*1..2]->(t) RETURN t.form LIMIT 9999', "limit-cap")
    expect_rejected("reject missing param",
                    "MATCH (h:Concept {form:$lemma})-[:CSKG*1..2]->(t) RETURN t.form LIMIT 25", "param-missing")

    # --- Sentinel is an INDEPENDENT enforcement (AC-4): even a hand-built ParsedQuery that bypassed
    #     the parser is caught by policy ---
    bypass = ParsedQuery(anchor_var="h", anchor_label="Concept", anchor_prop="form",
                         anchor_value="rain", anchor_is_param=False, rel_type="CSKG",
                         hop_min=1, hop_max=HOP_CAP + 5, relation_filter=None, relation_is_param=False,
                         tail_var="t", return_var="t", return_prop="form", limit=LIMIT_CAP + 500)
    try:
        sentinel_check(bypass)
        check("Sentinel catches parser-bypass hop cap", False, "sentinel did not deny")
    except SentinelDenied as e:
        check("Sentinel catches parser-bypass hop cap", e.code == "policy-hop-cap", f"got {e.code}")

    print(f"\n{_passed} passed, {_failed} failed")
    return 1 if _failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
