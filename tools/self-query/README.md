# self-query (WO-A3, RAG GAP #80)

The **vector self-query** construction verb of the advanced-RAG reference architecture (the
"self-query retriever" pattern). Turns a natural-language question into
`{semantic_query, metadata_filter}`, where the filter is a **Qdrant-acceptable** `{must, must_not}`
shape over a *declared* field schema and a supported operator subset. Hard-rejects filters over
undeclared fields / unsupported operators with stable reason codes (fail-closed — never a silent
full-scan). Closes the `GAP` verdict for element #3 (vector self-query) in the conformance matrix
(#78), and replaces the v0.1 stub the `query-router` (#77) emitted for
`construction_verb="self-query"`.

Consume-not-fork: the emitted filter shape is exactly what memoryd sends to Qdrant
(`prophet-platform/apps/memoryd/src/memoryd/qdrant_index.py`, collection `memorymesh-recall`:
`{'key':..,'match':{'value':..}}` / `match:{any}` / `range` / `is_empty`). The AgenticaForge
`MetadataFilter` fork's `$eq/$ne/$gt/$gte/$lt/$lte/$in/$nin/$exists` operator vocabulary is reused as
**reference only** — not a dependency.

## Pieces

| File | Role |
|---|---|
| `self_query.py` | `compile_filter(constraints, schema)` (validate+compile a MongoDB-style constraint set → Qdrant filter) **and** `build_self_query(question, schema)` (NL→`{semantic_query, metadata_filter}`). Two declared schemas: `MEMORYMESH_SCHEMA`, `CORPUS_SCHEMA`. |
| `fixtures/qdrant_fixture.py` | A tiny evaluator for the Qdrant filter shape + representative points, so a constructed filter executes and its hits are asserted (no live Qdrant). |
| `tests/conformance_test.py` | 25 checks, teeth both ways (implied filters extracted + executed against fixture points; undeclared field / unsupported op / bad operand rejected with the expected code; unrecognised phrasing → clean semantic-only passthrough). Run: `python3 tests/conformance_test.py`. |
| `query_self.proto` | triRPC IDL for the `SelfQueryConstructor.BuildSelfQuery` verb. |

## Operator subset & mapping

`$eq`→`must match:{value}`, `$ne`→`must_not match:{value}`, `$in`→`must match:{any}`,
`$nin`→`must_not match:{any}`, `$gt/$gte/$lt/$lte`→`must range:{...}` (merged per field),
`$exists:true`→`must_not is_empty`, `$exists:false`→`must is_empty`.

Rejected (stable code): `unknown-field` (undeclared), `unsupported-operator`, `enum-value`
(value not in a declared enum), `operand-type` (e.g. int range with a string, `$in` with a non-list),
`empty`.

NL extraction (v0.1 rules; LLM extractor is the documented seam): `memory_class` enum words,
temporal `after/before/in <year>` (→ date range on `created_at`, or int range on a `year` field),
`tagged <t>`, `in domain <d>`, and explicit `field:value` (which is where naming an **undeclared**
field is rejected). Anything unrecognised is left in `semantic_query` (clean passthrough).

## Wiring

Behind `query-router`'s `self-query` verb: `router.construct_query(choice, question=...)` calls
`build_self_query`. Path-filtered CI (`.github/workflows/self-query.yml`, and the `query-router.yml`
paths) gates the suite.

## Runtime (out of scope here — filed)

Live execution against a running Qdrant is a runtime concern (no live writes from this contract).
Tracked as a follow-up issue to @mdheller.

Refs #33, #78, #80.
