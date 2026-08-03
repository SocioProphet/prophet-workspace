"""Query Router contract — the RAG Routing layer (WO-A2 of ADR-0001, Open Agent Continuum).

The advanced-RAG reference architecture puts a **Routing** stage in front of query construction: a
natural-language question is first routed to a *backend* (and thus a construction verb) before any
store-specific query is built. Two routers, exactly as in the diagram:

  * LOGICAL ROUTE  — a router picks the data source. v0.1 is a transparent signal-rule router
    (relational→text-to-sql, graph→cypher, vector→self-query). An LLM router is the documented seam
    (same shape as `cypher_subset`'s regex-v0.1-with-a-cost-model-seam). Fail-closed: no signal ⇒
    ABSTAIN, never a silent default.
  * SEMANTIC ROUTE — embed the query in a PINNED space, cosine-nearest exemplar prompt wins IFF its
    margin over the runner-up ≥ threshold, else ABSTAIN (the descend-abstain discipline of the
    fibered-retrieval router: decline rather than route wrong).

The diagram's "Semantic Route: Graph DB → Vector DB" is encoded as a declared FALLBACK edge: if the
chosen backend cannot serve the query, the route falls back along `FALLBACK` and records it.

Every routing decision is emitted as a hash-chained, tamper-evident **RouteDecision** on the estate
receipt spine — this CONSUMES the proof-artifact-spine ledger discipline (`sha256`/`canonical`/
`verify_ledger`, SHA-256 = FIPS-180-4), it does not fork it. The graph route's constructed query is
validated against the real `cypher-atomspace-gateway` parser, so the router provably hands the
downstream gateway a query it will accept (consume-not-fork of WO-A).

Run the teeth:  python3 tests/conformance_test.py
"""
from __future__ import annotations

import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

from embedding import EmbeddingSpaceMismatch, PinnedSpace, cosine

# --- consume sibling estate contracts (consume-not-fork) --------------------------------------------
_TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in ("proof-artifact-spine", "cypher-atomspace-gateway"):
    sys.path.insert(0, os.path.join(_TOOLS, _p))

# proof-artifact-spine: reuse the append-only, tamper-evident ledger discipline verbatim.
from proof_artifact import GENESIS_PREV, _last_entry, canonical, sha256, verify_ledger  # noqa: E402
# cypher-atomspace-gateway: reuse the WO-A safe-subset parser to VALIDATE the graph handoff.
from cypher_subset import CypherRejected, parse as parse_cypher  # noqa: E402


# --- backends + construction verbs (the three stores in the reference diagram) ----------------------
@dataclass(frozen=True)
class Backend:
    name: str
    construction_verb: str  # what query-construction the downstream must run for this store


RELATIONAL = Backend("relational", "text-to-sql")
GRAPH = Backend("graph", "cypher")
VECTOR = Backend("vector", "self-query")

BACKENDS: dict[str, Backend] = {b.name: b for b in (RELATIONAL, GRAPH, VECTOR)}

# The diagram's Semantic Route "Graph DB → Vector DB": when the primary backend can't serve, fall
# back along this edge (graph misses a concept ⇒ try dense/vector recall). Declared, not implicit.
FALLBACK: dict[str, str] = {"graph": "vector"}

# Semantic-margin required for the semantic route to commit rather than abstain.
DEFAULT_MARGIN = 0.05


class RouteAbstained(Exception):
    """The router declined to route (fail-closed). `.code` is a stable reason code."""

    def __init__(self, code: str, message: str):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


@dataclass
class RouteChoice:
    backend: str
    construction_verb: str
    method: str                       # "logical" | "semantic"
    scores: dict = field(default_factory=dict)
    fallback: dict | None = None      # {"from":..., "to":..., "reason":...} when a fallback fired
    plan: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"backend": self.backend, "constructionVerb": self.construction_verb,
                "method": self.method, "scores": self.scores, "fallback": self.fallback,
                "plan": self.plan}


# --- LOGICAL ROUTE ----------------------------------------------------------------------------------
# v0.1 signal rules. Each backend has whole-word/substring signals; the LLM router is the seam that
# replaces this scoring while keeping the fail-closed contract (0 signal ⇒ abstain).
_SIGNALS: dict[str, tuple[str, ...]] = {
    "relational": ("how many", "count", "number of", "total", "sum of", "average", "avg",
                   "per ", " by ", "top ", "how much", "aggregate", "group by"),
    "graph": ("related to", "connected", "connection", "relationship", "path between", "how is",
              "neighbors", "neighbours", "is a ", "kind of", "part of", "causes", "caused by",
              "linked to", "hops"),
    "vector": ("find", "search", "documents about", "passages", "similar", "about ", "explain",
               "describe", "summarize", "what does", "papers on"),
}


class LogicalRouter:
    """Pick a backend from NL signals. Fail-closed: no signal ⇒ RouteAbstained('route-no-backend')."""

    def __init__(self, signals: dict[str, tuple[str, ...]] | None = None):
        self.signals = signals or _SIGNALS

    def route(self, query: str) -> RouteChoice:
        if not query or not query.strip():
            raise RouteAbstained("empty-query", "empty query")
        q = " " + query.lower().strip() + " "
        scores = {name: sum(1 for s in sigs if s in q) for name, sigs in self.signals.items()}
        best = max(scores, key=lambda k: scores[k])
        if scores[best] == 0:
            raise RouteAbstained("route-no-backend",
                                 "no backend signal matched (fail-closed, not a silent default)")
        b = BACKENDS[best]
        return RouteChoice(backend=b.name, construction_verb=b.construction_verb, method="logical",
                           scores=scores,
                           plan=[f"logical: signals={scores}", f"chose {b.name}→{b.construction_verb}"])


# --- SEMANTIC ROUTE ---------------------------------------------------------------------------------
@dataclass(frozen=True)
class Exemplar:
    """A prompt exemplar stored AS A VECTOR in the pinned space (query-by-vector, never re-embed)."""
    name: str
    backend: str
    vector: list[float]


class SemanticRouter:
    """Route by cosine to exemplar prompt-embeddings in ONE pinned space (#602 discipline).

    All exemplars AND the query must share `space`. A query vector of a foreign dimension is rejected
    with `embedding-space-mismatch` — not silently cosine-missed. Below-margin ⇒ abstain.
    """

    def __init__(self, space: PinnedSpace, exemplars: list[Exemplar], margin: float = DEFAULT_MARGIN):
        if not exemplars:
            raise ValueError("semantic router needs at least one exemplar")
        for ex in exemplars:                       # the pin covers the exemplar embed path too (#602)
            space.check(ex.vector, where=f"exemplar[{ex.name}]")
        self.space = space
        self.exemplars = exemplars
        self.margin = margin

    def route(self, query_vec: list[float]) -> RouteChoice:
        self.space.check(query_vec, where="query")  # the pin covers the query embed path (#602)
        ranked = sorted(((cosine(query_vec, ex.vector), ex) for ex in self.exemplars),
                        key=lambda t: t[0], reverse=True)
        (top_score, top), = ranked[:1]
        runner = ranked[1][0] if len(ranked) > 1 else -1.0
        margin = top_score - runner
        scores = {ex.name: round(s, 4) for s, ex in ranked}
        if margin < self.margin:
            raise RouteAbstained("route-ambiguous",
                                 f"top margin {margin:.4f} < {self.margin} (decline, don't route wrong)")
        b = BACKENDS[top.backend]
        return RouteChoice(backend=b.name, construction_verb=b.construction_verb, method="semantic",
                           scores=scores,
                           plan=[f"semantic: cosine={scores}", f"margin={margin:.4f}≥{self.margin}",
                                 f"chose {top.name}→{b.name}"])


# --- FALLBACK (Semantic Route: Graph DB → Vector DB) ------------------------------------------------
def apply_fallback(choice: RouteChoice, available: set[str]) -> RouteChoice:
    """If `choice.backend` is not available, fall back along FALLBACK. Fail-closed if no edge exists."""
    if choice.backend in available:
        return choice
    nxt = FALLBACK.get(choice.backend)
    if nxt is None or nxt not in available:
        raise RouteAbstained("route-unavailable",
                             f"backend '{choice.backend}' unavailable and no usable fallback edge")
    b = BACKENDS[nxt]
    return RouteChoice(backend=b.name, construction_verb=b.construction_verb, method=choice.method,
                       scores=choice.scores,
                       fallback={"from": choice.backend, "to": nxt, "reason": "backend-unavailable"},
                       plan=choice.plan + [f"fallback {choice.backend}→{nxt} (unavailable)"])


# --- construction handoff (prove the route hands a VALID query to the downstream store) --------------
def construct_query(choice: RouteChoice, *, lemma: str) -> str:
    """Build the store-specific query stub for the chosen verb.

    For the GRAPH backend the produced Cypher is validated against the REAL cypher-atomspace-gateway
    parser, so a graph route provably hands WO-A a query it accepts (raises CypherRejected otherwise).
    text-to-sql / self-query are v0.1 stubs (the NL→SQL and NL→filter builders are tracked gaps).
    """
    if choice.construction_verb == "cypher":
        cy = f'MATCH (h:Concept {{form:"{lemma}"}})-[:CSKG*1..2]->(t) RETURN t.form LIMIT 25'
        parse_cypher(cy)                # teeth: the gateway MUST accept what the router constructs
        return cy
    if choice.construction_verb == "text-to-sql":
        return f"SELECT * FROM facts WHERE subject = '{lemma}' LIMIT 25"      # stub (NL→SQL is a gap)
    if choice.construction_verb == "self-query":
        return f'{{"query": "{lemma}", "filter": {{}}}}'                       # stub (NL→filter is a gap)
    raise RouteAbstained("unknown-verb", f"no constructor for verb '{choice.construction_verb}'")


# --- RouteDecision record (hash-chained on the shared receipt spine) ---------------------------------
RECORD_TYPE = "RouteDecision"


def emit_route_decision(ledger: Path, *, query: str, choice: RouteChoice, agent: str) -> dict:
    """Append a hash-chained RouteDecision. Chains identically to ProofArtifact so `verify_ledger`
    (imported from the spine) validates it — one spine, one more record type."""
    ledger = Path(ledger)
    prev = _last_entry(ledger)
    prev_hash = prev["entryHash"] if prev else GENESIS_PREV
    seq = (prev["ledgerSeq"] + 1) if prev else 0
    body = {
        "recordType": RECORD_TYPE,
        "ledgerSeq": seq,
        "ledgerPrevHash": prev_hash,
        "emittedAt": round(time.time(), 3),
        "agent": agent,
        "inputHash": sha256(query),
        "route": choice.to_dict(),
    }
    body["entryHash"] = sha256(prev_hash + canonical(body))
    with open(ledger, "a", encoding="utf-8") as f:
        f.write(canonical(body) + "\n")
    return body


def route(query: str, *, semantic_router: SemanticRouter | None = None,
          query_vec: list[float] | None = None, available: set[str] | None = None,
          logical_router: LogicalRouter | None = None) -> RouteChoice:
    """Convenience: semantic route when a query vector is supplied, else logical; then fallback."""
    if semantic_router is not None and query_vec is not None:
        choice = semantic_router.route(query_vec)
    else:
        choice = (logical_router or LogicalRouter()).route(query)
    if available is not None:
        choice = apply_fallback(choice, available)
    return choice
