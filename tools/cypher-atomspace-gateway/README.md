# cypher-atomspace-gateway (WO-A)

The **Cypher façade** over the estate's canonical graph. An agent (Sherlock Scout / Loom) asks the
knowledge substrate in a small, safe Cypher subset; the gateway parses it, enforces caps at two
independent layers, translates it to an Atomese-style bounded traversal, and executes it against
**HellGraph** (our native local graph DB — the AtomSpace-canonical role is realised by HellGraph).

WO-A of [ADR-0001 — Open Agent Continuum](../../docs/adr/ADR-0001-open-agent-continuum.md). This is
the contract + a runnable reference; the live HellGraph binding is the runtime follow-up (tracked,
assigned).

## Pieces

| File | Role |
|---|---|
| `cypher_subset.py` | Parse + validate the safe subset (v0.1); hard-reject mutation/procedures/unbounded-hops/missing-LIMIT with stable reason codes. Gateway-side caps. |
| `gateway.py` | `Graph.QueryCypher(query, params, adapter)` — parse → **independent Sentinel re-check** → bind params → translate → execute → `{rows, plan, row_count}`. |
| `adapter.py` | `GraphAdapter` interface (HellGraph-compatible) + `InMemoryFixtureAdapter` (conformance drop-in) + `HellGraphClientAdapter` (documented seam for the vendored client). Atomese↔HellGraph mapping. |
| `fixtures/cskg_mini.json` | Tiny CSKG (ConceptNet/ATOMIC-style) for conformance. |
| `tests/conformance_test.py` | 17 checks, teeth both ways (correct traversals + rejections). Run: `python3 tests/conformance_test.py`. |
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

## Runtime follow-up (tracked + assigned)

`HellGraphClientAdapter` is a documented seam. Binding the vendored HellGraph client (upsert node/edge,
bounded BFS by edge type filtered by relation) makes this live — the conformance semantics above are the
contract that binding must honour. See the tracked issues linked from ADR-0001's WO register.
