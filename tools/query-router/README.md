# query-router (WO-A2)

The **Routing layer** of the advanced-RAG reference architecture, as an estate contract. It sits IN
FRONT of query construction: a natural-language question is first routed to a *backend* (and therefore
a construction verb) before any store-specific query is built.

WO-A2 of [ADR-0001 — Open Agent Continuum](../../docs/adr/ADR-0001-open-agent-continuum.md). This is
the contract + a runnable reference; it **consumes**, and does not fork, the two landed pieces it
depends on:

- **WO-A `cypher-atomspace-gateway`** — the graph route's constructed Cypher is validated by the real
  `cypher_subset.parse`, so a graph route provably hands the gateway a query it accepts.
- **WO-B `proof-artifact-spine`** — every decision is a hash-chained `RouteDecision` emitted with the
  spine's `sha256`/`canonical`/`verify_ledger` (SHA-256 = FIPS-180-4). One spine, one more record type.

## Why this exists (audit finding)

An estate audit against the reference architecture found the Routing layer was the weakest link: the
only *logical* routers are Noetica's knowledge-type / intent routers (live, but Noetica-internal); the
only *semantic* router on disk lives in a non-owned fork and is **unwired**; and there is **no**
graph→vector semantic route at all. This module provides the first owned, CI-gated routing contract.

## Pieces

| File | Role |
|---|---|
| `router.py` | `LogicalRouter` (signal-rule v0.1, LLM seam) + `SemanticRouter` (cosine-to-exemplar in a pinned space) + `apply_fallback` (the Graph DB → Vector DB edge) + `emit_route_decision` (hash-chained on the shared spine) + `construct_query` (validates the graph handoff against WO-A). |
| `embedding.py` | `PinnedSpace` + `FixtureEmbedder` — the #602 embedding-space discipline as an enforceable contract (query-by-vector; foreign-dimension vectors are rejected, not silently cosine-missed). |
| `tests/conformance_test.py` | Teeth both ways. Run: `python3 tests/conformance_test.py`. |
| `route_decision.proto` | triRPC IDL for the `Route.Decide` verb (fronts `Graph.QueryCypher`). |

## The two routes (reference diagram)

- **Logical route** — a router picks the data source. v0.1 is a transparent signal-rule router
  (`relational`→text-to-sql, `graph`→cypher, `vector`→self-query); an LLM router is the documented
  seam. **Fail-closed:** no signal ⇒ `route-no-backend`, never a silent default.
- **Semantic route** — embed the query in a `PinnedSpace`, take the cosine-nearest exemplar prompt IFF
  its margin over the runner-up ≥ threshold, else abstain (`route-ambiguous`). This is the
  descend-abstain discipline (decline rather than route wrong).
- **Graph DB → Vector DB** — `FALLBACK = {"graph": "vector"}`: when the chosen backend can't serve,
  the route falls back along the declared edge and records it on the decision; no usable edge ⇒
  `route-unavailable` (fail-closed).

## Teeth (both ways)

Positive: each of the three questions routes to the right backend+verb; the graph route's Cypher
parses in the WO-A gateway; the semantic route commits on a clear margin; the graph→vector fallback
fires; `RouteDecision`s chain and `verify_ledger` accepts them.

Negative (stable reason codes): `empty-query`, `route-no-backend`, `route-ambiguous`,
`embedding-space-mismatch` (a foreign-space query **and** a foreign-space exemplar — the #602 pin
covers every embed path), `route-unavailable`, and a tampered `RouteDecision` ledger breaks the chain.

## Runtime follow-up (tracked)

The LLM logical router, the NL→SQL and NL→filter constructors (`text-to-sql` / `self-query` are v0.1
stubs here), and binding the real sovereign embedder behind `PinnedSpace` are tracked gaps from the
RAG conformance audit (issues filed under the ADR-0001 WO register). `sherlock-scout` (WO-D), which
today hard-codes the graph path, is the intended first consumer of `Route.Decide`.
