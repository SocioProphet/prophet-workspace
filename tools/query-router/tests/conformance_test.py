"""Query-router conformance — runnable with `python3 tests/conformance_test.py` (no pytest dep).

Teeth verified BOTH ways (ADR-0001 discipline):
  POSITIVE — the three reference-diagram routes resolve to the right backend+verb; the graph route's
             constructed Cypher is ACCEPTED by the real cypher-atomspace-gateway parser; the semantic
             route commits when the margin is clear; the graph→vector fallback fires; RouteDecisions
             chain and verify on the shared receipt spine.
  NEGATIVE — empty query, no-signal, ambiguous-margin, foreign embedding space (#602), and a tampered
             RouteDecision ledger are all REJECTED with the expected stable code / broken chain.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
sys.path.insert(0, PKG)

# router.py adds the sibling WO-A gateway + WO-B spine dirs to sys.path on import; import it first so
# the consumed modules below (cypher_subset / proof_artifact) resolve.
from router import (  # noqa: E402
    Exemplar, LogicalRouter, SemanticRouter, RouteAbstained, apply_fallback, construct_query,
    emit_route_decision, route,
)
from cypher_subset import CypherRejected  # noqa: E402  (from the consumed WO-A gateway)
from embedding import EmbeddingSpaceMismatch, FixtureEmbedder, PinnedSpace  # noqa: E402
from proof_artifact import verify_ledger  # noqa: E402  (the consumed spine verifier)

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


def expect_abstain(name: str, fn, code: str) -> None:
    try:
        fn()
        check(name, False, f"expected abstain {code}, but it succeeded")
    except (RouteAbstained, EmbeddingSpaceMismatch, CypherRejected) as e:
        got = getattr(e, "code", "?")
        check(name, got == code, f"expected {code}, got {got}")


def main() -> int:
    lr = LogicalRouter()

    # --- POSITIVE: logical route picks each of the three stores in the diagram -----------------------
    c_graph = lr.route("how is rain related to flooding")
    check("logical→graph (relational-connection question)",
          c_graph.backend == "graph" and c_graph.construction_verb == "cypher", str(c_graph.to_dict()))
    c_sql = lr.route("how many storms per region last year")
    check("logical→relational (aggregation question)",
          c_sql.backend == "relational" and c_sql.construction_verb == "text-to-sql", str(c_sql.to_dict()))
    c_vec = lr.route("find documents about coastal erosion")
    check("logical→vector (semantic-search question)",
          c_vec.backend == "vector" and c_vec.construction_verb == "self-query", str(c_vec.to_dict()))

    # --- POSITIVE: the graph route hands the REAL gateway a query it accepts (consume-not-fork WO-A) -
    cy = construct_query(c_graph, lemma="rain")
    check("graph route's constructed Cypher parses in cypher-atomspace-gateway",
          "MATCH" in cy and "LIMIT 25" in cy, cy)

    # --- POSITIVE: the relational verb hands the SQL store a SAFE, parameterised query (WO-A3 #79) ---
    ss = construct_query(c_sql, question="how many fact memories are there")
    check("text-to-sql verb → parameterised SELECT-only (COUNT), value bound not interpolated",
          ss.sql.upper().startswith("SELECT COUNT(*)") and ss.params == ["fact"]
          and "DROP" not in ss.sql.upper(), f"{ss.sql} :: {ss.params}")

    # --- POSITIVE: the vector verb hands Qdrant a {semantic_query, metadata_filter} (WO-A3 #80) ------
    sqf = construct_query(c_vec, question="find fact memories about coastal erosion")
    check("self-query verb → residual query + Qdrant-shaped filter over a declared field",
          sqf.metadata_filter.get("must") == [{"key": "memory_class", "match": {"value": "fact"}}]
          and "erosion" in sqf.semantic_query.lower(), str(sqf.to_dict()))

    # --- POSITIVE: semantic route commits when a query is clearly nearest one exemplar --------------
    space = PinnedSpace(dims=64)
    emb = FixtureEmbedder(space)
    exemplars = [
        Exemplar("agg-prompt", "relational", emb.embed("count total number sum average per group by")),
        Exemplar("graph-prompt", "graph", emb.embed("related connected relationship path neighbours isa")),
        Exemplar("doc-prompt", "vector", emb.embed("find search documents passages similar about explain")),
    ]
    sr = SemanticRouter(space, exemplars, margin=0.02)
    q_semantic = emb.embed("find documents similar to this about erosion")
    c_sem = sr.route(q_semantic)
    check("semantic→vector (nearest doc exemplar, margin met)", c_sem.backend == "vector",
          str(c_sem.to_dict()))
    check("semantic route records cosine scores + method", c_sem.method == "semantic" and c_sem.scores,
          str(c_sem.scores))

    # --- POSITIVE: Graph DB → Vector DB fallback (the diagram's semantic-route edge) ----------------
    fell = apply_fallback(c_graph, available={"vector"})          # graph unavailable, vector is
    check("graph→vector fallback fires when graph backend unavailable",
          fell.backend == "vector" and fell.fallback and fell.fallback["from"] == "graph",
          str(fell.fallback))
    no_fb = apply_fallback(c_graph, available={"graph", "vector"})  # graph available: no fallback
    check("no fallback when chosen backend is available", no_fb.fallback is None, str(no_fb.to_dict()))

    # --- POSITIVE: RouteDecisions chain + verify on the shared receipt spine ------------------------
    with tempfile.TemporaryDirectory() as td:
        ledger = Path(td) / "route.ledger.jsonl"
        r0 = emit_route_decision(ledger, query="how is rain related to flooding", choice=c_graph,
                                 agent="query-router")
        r1 = emit_route_decision(ledger, query="find documents about erosion", choice=c_vec,
                                 agent="query-router")
        check("RouteDecision seq monotonic + chained", r0["ledgerSeq"] == 0 and r1["ledgerSeq"] == 1
              and r1["ledgerPrevHash"] == r0["entryHash"], f"{r0['ledgerSeq']},{r1['ledgerSeq']}")
        ok, msg = verify_ledger(ledger)
        check("spine verify_ledger accepts the RouteDecision chain", ok, msg)

        # NEGATIVE: tamper the record → the shared spine verifier breaks the chain (tamper-evident)
        lines = ledger.read_text().splitlines()
        lines[0] = lines[0].replace('"backend":"graph"', '"backend":"vector"')
        ledger.write_text("\n".join(lines) + "\n")
        ok2, _ = verify_ledger(ledger)
        check("tampered RouteDecision breaks the hash chain", not ok2, "verify still accepted a tamper")

    # --- NEGATIVE: fail-closed abstains (teeth) -----------------------------------------------------
    expect_abstain("reject empty query", lambda: lr.route("   "), "empty-query")
    expect_abstain("reject no-signal query (no silent default)",
                   lambda: lr.route("xyzzy plugh frobnicate"), "route-no-backend")

    # NEGATIVE: ambiguous semantic margin → abstain rather than route wrong (descend-abstain)
    sr_strict = SemanticRouter(space, exemplars, margin=0.99)
    expect_abstain("reject ambiguous semantic margin", lambda: sr_strict.route(q_semantic),
                   "route-ambiguous")

    # NEGATIVE: the #602 teeth — a query embedded in a FOREIGN space is rejected, not cosine-missed
    foreign = FixtureEmbedder(PinnedSpace(dims=32)).embed("find documents about erosion")
    expect_abstain("reject foreign-space query vector (#602 pin)", lambda: sr.route(foreign),
                   "embedding-space-mismatch")
    # and the pin covers the exemplar embed path too
    expect_abstain("reject foreign-space exemplar (#602 pin covers exemplars)",
                   lambda: SemanticRouter(space, [Exemplar("bad", "vector", foreign)]),
                   "embedding-space-mismatch")

    # NEGATIVE: fallback with no usable edge is fail-closed, not a silent wrong route
    expect_abstain("reject fallback with no usable edge",
                   lambda: apply_fallback(c_graph, available={"relational"}), "route-unavailable")

    # --- convenience route() dispatch (semantic when a vector is given, else logical) ---------------
    conv = route("how is rain related to flooding", available={"graph"})
    check("route() logical dispatch + available-passthrough", conv.backend == "graph",
          str(conv.to_dict()))

    print(f"\n{_passed} passed, {_failed} failed")
    return 1 if _failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
