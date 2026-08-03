"""Graph→Vector *selective* cross-source route (WO-A2, issue #81; refs #77, #76, #33, #78).

PR #77 landed the routing *contract*: a declared `FALLBACK = {"graph": "vector"}` edge that fires only
when the graph backend is *administratively unavailable* (`apply_fallback`). That is a real edge, but it
is not yet a real *selective fuse*: the graph→vector decision is not driven by whether the graph could
actually answer *this query*. This module makes the edge **query-driven** and turns it into a selective
FUSE:

  1. attempt GRAPH retrieval over the WO-A `cypher-atomspace-gateway` path (the constructed Cypher is
     validated by the real `cypher_subset.parse`, so we provably hand the gateway a query it accepts);
  2. decide advance-vs-fall with the REAL fibered **descend-abstain** conformal gate — this file is the
     first real importer of `agentplane/tools/fiber_retrieval.py` (built, previously zero importers): its
     conformal `ACCEPT`/abstain over the graph result's nonconformity is the fall signal, exactly the
     `descend` discipline (`fiber_retrieval.py:138`), consumed not forked;
  3. when the graph is confident → route to GRAPH and DO NOT touch the vector store (teeth);
     when the graph misses/abstains → descend to VECTOR;
     when the graph returns weak-but-nonempty hits AND vector returns → **FUSE** (union, graph-precision
     first, vector-recall second) rather than replace;
     when neither returns → **explicit ABSTAIN** (a `RouteDecision` is still emitted, then
     `RouteAbstained` is raised — never a silent empty result).

Every outcome — graph, vector-fallback, fuse, abstain — is emitted as a hash-chained `RouteDecision` on
the shared proof-artifact spine (`emit_route_decision`; SHA-256 = FIPS-180-4). The live HellGraph graph
retriever and the live vector retriever are dependency-injected callables (the seam), so this module is
fully exercised by fixtures in conformance; wiring the live stores is tracked as a runtime task.

Run the teeth:  python3 tests/selective_route_conformance.py
"""
from __future__ import annotations

import importlib
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

# --- consume the WO-A2 router contract (sibling, same repo) — do not fork it ------------------------
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
from router import (  # noqa: E402
    BACKENDS, GRAPH, VECTOR, RouteAbstained, RouteChoice, construct_query, emit_route_decision,
)


# The pinned VENDORED copy of the agentplane fiber_retrieval closure (consume-not-fork). It is a
# byte-for-byte snapshot of `agentplane/tools/*.py` at a recorded commit, SHA-256-pinned in
# `vendor/VENDOR.md` and gated by `tests/vendor_consume_guard.py` (the source-os#317 drift guard). It is
# the FALLBACK: a live agentplane checkout still wins (below), but the vendored copy lets the full teeth
# run in CI with no cross-repo checkout and no ESTATE_CHECKOUT_TOKEN (#96).
_VENDOR = os.path.join(_HERE, "vendor", "agentplane")


# --- give fiber_retrieval its FIRST real importer (consume-not-fork, cross-repo by path) ------------
def _resolve_fiber_retrieval():
    """Locate and import the REAL `agentplane` `fiber_retrieval` (with its `conformal_gate`,
    `fiber_projection`, `stopgate_artifact` closure).

    Consume-not-fork: we import the actual module, never an edited fork. Resolution order:
    `$AGENTPLANE_TOOLS`, then agentplane as a sibling repo under the common dev root (a LIVE checkout
    wins so local edits are exercised), then finally the SHA-256-pinned VENDORED copy under
    `vendor/agentplane/` — the byte-identical snapshot that lets CI run the cross-repo teeth without a
    token (#96). Fail-closed with the attempted paths named, so even a missing vendor dir is a loud,
    actionable error — never a silent fallback that would quietly drop the abstention gate.
    """
    tried: list[str] = []
    candidates: list[str] = []
    env = os.environ.get("AGENTPLANE_TOOLS")
    if env:
        candidates.append(env)
    # Walk up from this file: at every ancestor, agentplane may be a sibling repo (`.../agentplane/tools`).
    # This resolves both a normal `<dev>/prophet-workspace` checkout and a `<dev>/_wt/<worktree>` one.
    cur = _HERE
    while True:
        candidates.append(os.path.join(cur, "agentplane", "tools"))
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent
    # Last: the pinned vendored copy (always present in-repo; the guard keeps it honest).
    candidates.append(_VENDOR)
    for c in candidates:
        cand = os.path.abspath(c)
        tried.append(cand)
        if os.path.isfile(os.path.join(cand, "fiber_retrieval.py")):
            if cand not in sys.path:
                sys.path.insert(0, cand)
            return importlib.import_module("fiber_retrieval")
    raise ImportError(
        "fiber_retrieval.py not found (its importer needs the real agentplane module, not a fork). "
        "Set AGENTPLANE_TOOLS to agentplane/tools, or restore the pinned vendor/ copy. Tried: "
        + ", ".join(tried))


# Imported at module load so the importer is REAL (not a lazy path that never fires). See #81.
fr = _resolve_fiber_retrieval()


# --- the abstention gate (the fibered descend-abstain discipline, built through fiber_retrieval) ----
# Default risk budget for the conformal gate; a confident graph result (~0.1 nonconformity) is ACCEPTed
# and an ambiguous/empty one (~0.9) abstains — the same calibration `fiber_retrieval` uses for descend.
DEFAULT_ALPHA = 0.10
# nonconformity assigned to an empty graph result: maximally non-conforming ⇒ forces abstain/fall.
EMPTY_NONCONFORMITY = 1.0
_STOP = {"what", "who", "the", "a", "an", "is", "are", "was", "were", "of", "to", "in", "on", "how",
         "why", "did", "does", "do", "and", "or", "related", "connected", "about", "find", "between"}


def default_gate(alpha: float = DEFAULT_ALPHA):
    """Build the real split-CRC conformal gate via `fiber_retrieval.calibrate_gate` (its public seam).

    Calibrated so a low nonconformity (confident graph hit) yields `ACCEPT` and a high one yields the
    abstention verdict — identical to the gate `fiber_retrieval.descend` classifies against."""
    scores = [i / 100 for i in range(100)]
    correct = [s <= 0.4 for s in scores]
    return fr.calibrate_gate(scores, correct, alpha)


def _graph_confident(gate, nonconformity: float) -> bool:
    """True iff the descend-abstain gate ACCEPTs (advance on graph); False ⇒ abstain (fall to vector)."""
    return gate.classify(nonconformity) == fr.cg.ACCEPT


# --- retrieval source contract (the injected seam over live HellGraph + vector store) ---------------
@dataclass
class SourceHits:
    """Result of one retrieval source. `nonconformity` is LOW when the source is confident (the signal
    the descend-abstain gate classifies); an empty result is maximally non-conforming."""
    backend: str
    hits: list = field(default_factory=list)
    nonconformity: float = EMPTY_NONCONFORMITY
    meta: dict = field(default_factory=dict)

    @property
    def nonempty(self) -> bool:
        return bool(self.hits)


# A graph retriever is `(query, cypher) -> SourceHits`; a vector retriever is `(query) -> SourceHits`.
# Live HellGraph / vector-store bindings are dependency-injected (the runtime seam, tracked in #81).
GraphRetriever = Callable[[str, str], SourceHits]
VectorRetriever = Callable[[str], SourceHits]


@dataclass
class CrossSourceResult:
    """The selective route's outcome: which backend(s) served, the fused hits, the routing choice that
    was recorded, and the emitted `RouteDecision` receipt."""
    backend: str                       # "graph" | "vector" | "graph+vector"
    hits: list
    choice: RouteChoice
    fused: bool
    decision: dict                     # the hash-chained RouteDecision record on the spine
    graph: SourceHits
    vector: Optional[SourceHits] = None


def _lemma(query: str) -> Optional[str]:
    toks = [t for t in re.findall(r"[a-z][a-z0-9\-]*", (query or "").lower()) if t not in _STOP]
    return toks[0] if toks else None


def _fuse(graph_hits: list, vector_hits: list, key: Callable[[object], object]) -> list:
    """Union with graph-precision first, vector-recall second; dedup by `key` (stable order)."""
    out, seen = [], set()
    for h in list(graph_hits) + list(vector_hits):
        k = key(h)
        if k in seen:
            continue
        seen.add(k)
        out.append(h)
    return out


def _default_key(h):
    if isinstance(h, dict):
        return h.get("id", h.get("form", repr(sorted(h.items()))))
    return h


def selective_route(query: str, *, graph_retriever: GraphRetriever, vector_retriever: VectorRetriever,
                    ledger: Path, agent: str = "query-router", gate=None,
                    fuse_key: Callable[[object], object] = _default_key) -> CrossSourceResult:
    """Query-driven graph→vector selective route + fuse, on the descend-abstain gate.

    Fail-closed: an empty query, and a genuine graph+vector miss, both ABSTAIN with a recorded
    `RouteDecision` and a raised `RouteAbstained` — never a silent empty result."""
    if not query or not query.strip():
        raise RouteAbstained("empty-query", "empty query")
    gate = gate if gate is not None else default_gate()
    ledger = Path(ledger)

    # 1) GRAPH attempt over the WO-A gateway path. construct_query validates the Cypher against the real
    #    cypher-atomspace-gateway parser (consume-not-fork of WO-A): we hand it a query it will accept.
    lemma = _lemma(query) or "concept"
    graph_choice = RouteChoice(backend=GRAPH.name, construction_verb=GRAPH.construction_verb,
                               method="selective", plan=[f"lemma={lemma}"])
    cypher = construct_query(graph_choice, lemma=lemma)
    g = graph_retriever(query, cypher)
    g.nonconformity = g.nonconformity if g.nonempty else EMPTY_NONCONFORMITY
    confident = g.nonempty and _graph_confident(gate, g.nonconformity)
    gate_verdict = fr.cg.ACCEPT if confident else fr.cg.ABSTAIN

    # 2a) GRAPH confident ⇒ advance on graph; DO NOT call the vector store (selective, not always-fuse).
    if confident:
        choice = RouteChoice(
            backend=GRAPH.name, construction_verb=GRAPH.construction_verb, method="selective",
            scores={"graph_nonconformity": round(g.nonconformity, 4), "gate": gate_verdict,
                    "graph_hits": len(g.hits)},
            plan=[f"graph gate={gate_verdict} (nonconf {g.nonconformity:.3f})",
                  "advance on graph; vector store not consulted"])
        decision = emit_route_decision(ledger, query=query, choice=choice, agent=agent)
        return CrossSourceResult(backend=GRAPH.name, hits=list(g.hits), choice=choice, fused=False,
                                 decision=decision, graph=g, vector=None)

    # 2b) graph abstains/misses ⇒ DESCEND to vector (query-driven fall, not admin-unavailable).
    v = vector_retriever(query)
    fall_reason = "graph-empty" if not g.nonempty else "graph-low-confidence"

    # both returned ⇒ FUSE (don't replace: keep the graph's precise hits, add vector recall).
    if g.nonempty and v.nonempty:
        fused = _fuse(g.hits, v.hits, fuse_key)
        choice = RouteChoice(
            backend="graph+vector", construction_verb="fuse", method="selective",
            scores={"graph_nonconformity": round(g.nonconformity, 4), "gate": gate_verdict,
                    "graph_hits": len(g.hits), "vector_hits": len(v.hits), "fused_hits": len(fused)},
            fallback={"from": GRAPH.name, "to": VECTOR.name, "reason": f"descend-abstain:{fall_reason}"},
            plan=[f"graph gate={gate_verdict} (nonconf {g.nonconformity:.3f}) ⇒ descend to vector",
                  f"FUSE graph({len(g.hits)})+vector({len(v.hits)})={len(fused)} (union, graph-first)"])
        decision = emit_route_decision(ledger, query=query, choice=choice, agent=agent)
        return CrossSourceResult(backend="graph+vector", hits=fused, choice=choice, fused=True,
                                 decision=decision, graph=g, vector=v)

    # only vector returned ⇒ VECTOR route (the query-driven graph→vector fallback).
    if v.nonempty:
        choice = RouteChoice(
            backend=VECTOR.name, construction_verb=VECTOR.construction_verb, method="selective",
            scores={"graph_nonconformity": round(g.nonconformity, 4), "gate": gate_verdict,
                    "graph_hits": len(g.hits), "vector_hits": len(v.hits)},
            fallback={"from": GRAPH.name, "to": VECTOR.name, "reason": f"descend-abstain:{fall_reason}"},
            plan=[f"graph gate={gate_verdict} (nonconf {g.nonconformity:.3f}) ⇒ descend to vector",
                  f"vector served {len(v.hits)} hits"])
        decision = emit_route_decision(ledger, query=query, choice=choice, agent=agent)
        return CrossSourceResult(backend=VECTOR.name, hits=list(v.hits), choice=choice, fused=False,
                                 decision=decision, graph=g, vector=v)

    # 2c) neither returned ⇒ EXPLICIT abstain. Record it on the spine, THEN raise (never silent empty).
    abstain = RouteChoice(
        backend="abstain", construction_verb="none", method="selective",
        scores={"graph_nonconformity": round(g.nonconformity, 4), "gate": gate_verdict,
                "graph_hits": 0, "vector_hits": 0},
        fallback={"from": GRAPH.name, "to": VECTOR.name, "reason": f"descend-abstain:{fall_reason}"},
        plan=[f"graph gate={gate_verdict} ⇒ descend to vector", "vector also empty ⇒ ABSTAIN"])
    emit_route_decision(ledger, query=query, choice=abstain, agent=agent)
    raise RouteAbstained("cross-source-miss",
                         "graph abstained and vector returned no hits (fail-closed, not a silent empty)")
