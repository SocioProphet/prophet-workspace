"""Selective graph→vector cross-source route conformance — `python3 tests/selective_route_conformance.py`.

Teeth both ways for issue #81 (refs #77, #76):
  POSITIVE — a graph-answerable query routes to GRAPH and the vector store is NEVER consulted; a
             graph-miss query DESCENDS to vector; a graph-weak + vector-hit query FUSES (union, both
             sources present); every route emits a `RouteDecision` that chains + verifies on the shared
             spine; the fall records the abstain reason; the fibered `descend`-abstain gate is the REAL
             `agentplane/tools/fiber_retrieval` module (its first real importer).
  NEGATIVE — an empty query abstains; a genuine graph+vector miss is an EXPLICIT abstain
             (`cross-source-miss`) with a recorded RouteDecision, not a silent empty result.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
sys.path.insert(0, PKG)

from router import RouteAbstained  # noqa: E402
from proof_artifact import verify_ledger  # noqa: E402  (consumed WO-B spine verifier)
import selective_route as sr  # noqa: E402  (imports fiber_retrieval at load → the first real importer)

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


class SpyVector:
    """A vector retriever that records whether it was called (teeth: graph-answerable ⇒ never called)."""

    def __init__(self, hits, nonconformity=0.2):
        self.hits = hits
        self.nonconformity = nonconformity
        self.calls = 0

    def __call__(self, query):
        self.calls += 1
        return sr.SourceHits(backend="vector", hits=list(self.hits), nonconformity=self.nonconformity)


def graph_returning(hits, nonconformity):
    def _g(query, cypher):
        # teeth: the router must hand us a Cypher the WO-A gateway accepts (already parsed upstream)
        assert cypher.startswith("MATCH") and "LIMIT 25" in cypher, cypher
        return sr.SourceHits(backend="graph", hits=list(hits), nonconformity=nonconformity)
    return _g


def main() -> int:
    # The deliverable's headline: fiber_retrieval now HAS a real importer, loaded at module import.
    check("fiber_retrieval is the real agentplane module (first real importer)",
          getattr(sr.fr, "__name__", None) == "fiber_retrieval"
          and hasattr(sr.fr, "descend") and hasattr(sr.fr, "calibrate_gate"),
          f"fr={getattr(sr.fr, '__file__', '?')}")
    check("selective route builds the REAL fibered descend-abstain conformal gate",
          type(sr.default_gate()).__name__ == "CalibratedGate")

    with tempfile.TemporaryDirectory() as td:
        ledger = Path(td) / "route.ledger.jsonl"

        # --- TEETH 1: graph-answerable ⇒ GRAPH, vector NEVER called -------------------------------
        spy = SpyVector(hits=[{"id": "v1"}])
        res = sr.selective_route("how is rain related to flooding",
                                 graph_retriever=graph_returning([{"id": "g1"}, {"id": "g2"}], 0.10),
                                 vector_retriever=spy, ledger=ledger)
        check("graph-answerable routes to graph", res.backend == "graph", res.backend)
        check("graph-answerable does NOT consult the vector store (selective, not always-fuse)",
              spy.calls == 0, f"vector called {spy.calls}x")
        check("graph route emits a RouteDecision on the spine", res.decision["recordType"] == "RouteDecision")
        check("graph route records the gate ACCEPT verdict",
              res.choice.scores.get("gate") == sr.fr.cg.ACCEPT, str(res.choice.scores))

        # --- TEETH 2: graph-miss (empty) ⇒ DESCEND to vector -------------------------------------
        spy2 = SpyVector(hits=[{"id": "v1"}, {"id": "v2"}])
        res2 = sr.selective_route("find documents about coastal erosion",
                                  graph_retriever=graph_returning([], sr.EMPTY_NONCONFORMITY),
                                  vector_retriever=spy2, ledger=ledger)
        check("graph-miss descends to vector", res2.backend == "vector" and spy2.calls == 1, res2.backend)
        check("graph-miss records the fallback edge + abstain reason",
              res2.choice.fallback and res2.choice.fallback["from"] == "graph"
              and res2.choice.fallback["to"] == "vector"
              and "graph-empty" in res2.choice.fallback["reason"], str(res2.choice.fallback))
        check("vector route returns the vector hits", [h["id"] for h in res2.hits] == ["v1", "v2"],
              str(res2.hits))

        # --- TEETH 3: graph weak-but-nonempty + vector hit ⇒ FUSE (don't replace) ----------------
        spy3 = SpyVector(hits=[{"id": "v1"}, {"id": "g1"}])  # note: g1 overlaps graph ⇒ dedup
        res3 = sr.selective_route("explain how storms relate to erosion",
                                  graph_retriever=graph_returning([{"id": "g1"}], 0.90),  # low confidence
                                  vector_retriever=spy3, ledger=ledger)
        check("both-hit fuses (graph+vector)", res3.backend == "graph+vector" and res3.fused, res3.backend)
        ids = [h["id"] for h in res3.hits]
        check("fuse is a UNION keeping graph precision first, vector recall second, deduped",
              ids == ["g1", "v1"], str(ids))
        check("fuse route records the abstain reason on the fallback edge",
              res3.choice.fallback and "low-confidence" in res3.choice.fallback["reason"],
              str(res3.choice.fallback))
        check("fuse route records both source hit-counts", res3.choice.scores.get("graph_hits") == 1
              and res3.choice.scores.get("vector_hits") == 2, str(res3.choice.scores))

        # --- every route so far emitted a RouteDecision; the chain verifies on the shared spine ---
        ok, msg = verify_ledger(ledger)
        check("all RouteDecisions chain + verify on the shared receipt spine", ok, msg)

        # NEGATIVE: tamper a RouteDecision ⇒ the shared spine verifier breaks the chain -----------
        lines = ledger.read_text().splitlines()
        lines[0] = lines[0].replace('"graph_hits":2', '"graph_hits":9')
        ledger.write_text("\n".join(lines) + "\n")
        ok2, _ = verify_ledger(ledger)
        check("tampered RouteDecision breaks the hash chain (tamper-evident)", not ok2,
              "verifier accepted a tamper")

        # --- TEETH 4: graph + vector BOTH miss ⇒ EXPLICIT abstain (not a silent empty) -----------
        clean = Path(td) / "abstain.ledger.jsonl"
        spy4 = SpyVector(hits=[])
        abstained = {"raised": False}
        try:
            sr.selective_route("xyzzy plugh frobnicate concept",
                               graph_retriever=graph_returning([], sr.EMPTY_NONCONFORMITY),
                               vector_retriever=spy4, ledger=clean)
        except RouteAbstained as e:
            abstained["raised"] = True
            abstained["code"] = e.code
        check("graph+vector miss RAISES an explicit RouteAbstained (not a silent empty)",
              abstained["raised"] and abstained.get("code") == "cross-source-miss", str(abstained))
        # the abstain is on the spine (explicit), not swallowed
        recs = [ln for ln in clean.read_text().splitlines() if ln.strip()]
        check("the abstain is RECORDED on the spine before raising (explicit, not silent)",
              len(recs) == 1 and '"backend":"abstain"' in recs[0], recs)
        ok3, msg3 = verify_ledger(clean)
        check("the abstain RouteDecision chain verifies", ok3, msg3)

        # NEGATIVE: empty query is fail-closed
        try:
            sr.selective_route("   ", graph_retriever=graph_returning([], 1.0),
                               vector_retriever=SpyVector([]), ledger=clean)
            check("empty query abstains", False, "did not abstain")
        except RouteAbstained as e:
            check("empty query abstains (empty-query)", e.code == "empty-query", e.code)

    print(f"\n{_passed} passed, {_failed} failed")
    return 1 if _failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
