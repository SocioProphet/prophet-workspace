# cypher-atomspace-gateway (WO-A)

The **Cypher façade** over the estate's canonical graph. An agent (Sherlock Scout / Loom) asks the
knowledge substrate in a small, safe Cypher subset; the gateway parses it, enforces caps at two
independent layers, translates it to an Atomese-style bounded traversal, and executes it against
**HellGraph** (our native local graph DB — the AtomSpace-canonical role is realised by HellGraph).

WO-A of [ADR-0001 — Open Agent Continuum](../../docs/adr/ADR-0001-open-agent-continuum.md). The
contract + a runnable reference (`InMemoryFixtureAdapter`) **and** the live HellGraph binding
(`HellGraphClientAdapter`) over the canonical `hellgraph-service` HTTP surface.

## Pieces

| File | Role |
|---|---|
| `cypher_subset.py` | Parse + validate the safe subset (v0.1); hard-reject mutation/procedures/unbounded-hops/missing-LIMIT with stable reason codes. Gateway-side caps. |
| `gateway.py` | `Graph.QueryCypher(query, params, adapter)` — parse → **independent Sentinel re-check** → bind params → translate → execute → `{rows, plan, row_count}`. |
| `adapter.py` | `GraphAdapter` interface (HellGraph-compatible) + `InMemoryFixtureAdapter` (conformance drop-in) + `HellGraphClientAdapter` (**live binding** over the hellgraph-service HTTP surface). Atomese↔HellGraph mapping. |
| `fixtures/cskg_mini.json` | Tiny CSKG (ConceptNet/ATOMIC-style) for conformance. |
| `tests/conformance_test.py` | 17 checks, teeth both ways (correct traversals + rejections). Run: `python3 tests/conformance_test.py`. |
| `tests/hellgraph_binding_test.py` | 12 checks that the live binding honours the fixture contract over the confirmed HTTP surface (fake by default; `HELLGRAPH_BASE_URL` runs it against a real hellgraph-service). Run: `python3 tests/hellgraph_binding_test.py`. |
| `graph_query_cypher.proto` | triRPC IDL for the `Graph.QueryCypher` verb. |

## Safe subset (v0.1)

Accepted: `MATCH (h:Concept {form:$lemma})-[:CSKG*1..2]->(t) RETURN t.form LIMIT 25` — one anchor
(label+prop), one bounded relationship (`*min..max`, `max <= 2`), optional `{relation:...}` filter,
`RETURN <var>.<prop>`, mandatory `LIMIT <= 100`.

Rejected: `CREATE/DELETE/SET/MERGE/REMOVE`, `CALL`, `WHERE/UNION/WITH` (deferred until a cost model
exists), unbounded or over-cap hops, missing/over-cap `LIMIT`. Caps are enforced at the gateway **and**
independently by Sentinel (AC-4).

## Mapping (Cypher ↔ Atomese ↔ HellGraph)

```
(n:Concept {form:"rain"})           ConceptNode "rain"          HellGraph node label=Concept form=rain
(h)-[:CSKG {relation:"IsA"}]->(t)   EvaluationLink              HellGraph typed edge IsA (h->t)
                                      (Predicate "IsA")           + TruthValue{strength,confidence}
                                      (List (Concept h)(Concept t))
```

TruthValue composes multiplicatively along a path (v0). Min-confidence vs product vs learned weighting
is a WO-B experiment.

## Runtime binding (live)

`HellGraphClientAdapter` consumes the canonical **`hellgraph-service`** (prophet-platform/apps/
hellgraph-service) — the same door the rest of the estate writes through (nugget-extractor's
`HellGraphWriter`, market-replay's emitter). Verified endpoints:

- `POST /api/graph/node` `{id, labels[], properties?}` — upsert (`upsert_concept`)
- `POST /api/graph/edge` `{label, from, to, properties?}` — typed edge carrying `{strength, confidence}` (`upsert_relation`)
- `GET  /api/graph/subgraph?label=Concept&limit=N` — induced subgraph; edge `.properties` round-trip, so
  `expand` rebuilds the local edge table and runs the **identical** bounded-BFS truth-composition the
  conformance suite pins (`InMemoryFixtureAdapter.expand`) — correctness by algorithm reuse.

`expand` currently pulls the Concept subgraph and BFS-es locally; a per-node out-edge read
(Gremlin `outE()`+`valueMap` over `POST /api/graph/gremlin`) is a mechanical, semantics-frozen swap
for incremental expansion. `httpx` is imported lazily, so the conformance suite runs with no HTTP dep.
