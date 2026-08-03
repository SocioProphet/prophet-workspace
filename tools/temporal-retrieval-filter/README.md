# temporal-retrieval-filter (GAP-2)

The **uniform temporal-correctness contract** for the estate. Given *any* ranked candidate set whose
items carry `(entity, relation, valid_from, superseded_by?/superseded_at?)`, it suppresses superseded
facts and returns the **most-recent (max `valid_from`) survivor** per `(entity, relation)` — so a
retrieval surface answers with the current fact, not a semantically-similar outdated one.

Closes **ADR-0002 §8 GAP-2** ([pw#84](../../docs/adr/ADR-0002-governed-cognition-functor.md), pw#76
item 1): temporal retrieval filter + fact supersession as a **uniform substrate capability**, not one
that lives only on the surface that shipped it.

## Consume-not-fork

`regis-entity-graph#20` shipped the invariant (`schemas/search/temporal-fact.schema.json` +
`tools/validate_temporal_supersession.py`: high-recall → suppress superseded → max-`valid_from` wins),
but welded to the `regis.search.temporal_fact.v0.1` schema. This module **lifts the same invariant** into
a schema-agnostic core; it does **not** re-derive a rival one:

- `DEFAULT_FIELD_MAP` uses regis vocabulary, so a regis fact flows through the default filter unchanged.
- The conformance suite pins this filter to regis#20's shipped `temporal_retrieve` as an **oracle**:
  `resolve()` returns regis's exact trace shape and, on regis facts, identical results.
- Follow-ups track regis#20 delegating to this shared core (one physical home) and per-surface wiring.

## The decoupling — `FieldMap`

Surfaces name the same concepts differently. A `FieldMap` maps a surface's field names onto the six
temporal concepts, so one filter serves them all:

| Concept | regis (default) | example RAG chunk |
|---|---|---|
| supersession key | `entity` / `relation` | `subject` / `predicate` |
| validity start | `valid_from` | `effective_from` |
| validity end | `valid_to` | `expired_at` |
| supersession pointer | `superseded_by` | `replaced_by` |
| supersession instant | `superseded_at` | `replaced_at` |

## Pieces

| File | Role |
|---|---|
| `temporal_retrieval_filter.py` | `FieldMap` (schema decoupling), `TemporalRetrievalFilter.apply/filter/resolve`, `validate_temporal` (the invariants JSON Schema can't express), `FilterResult`. Stdlib-only. |
| `tests/conformance_test.py` | Teeth both ways. Run: `python3 tests/conformance_test.py`. |
| `tests/fixtures/regis_ceo_supersession.facts.json` | Vendored regis#20 canonical fixture (data, not logic) for the teeth + oracle cross-check. |

## Teeth (`python3 tests/conformance_test.py` → 20/20)

1. **regis supersession** — John-Smith → Jenna-Brown: both surfaced (high-recall), John-Smith excluded
   (`superseded`), **Jenna Brown authoritative** (max `valid_from`).
2. **pass-through** — a ranked list with **no** temporal fields is returned **unchanged** (identity + order).
3. **fail-closed rejection** — `superseded_at < valid_from`, `valid_to < valid_from`, and a supersession
   marker with no `valid_from` to order against are all **rejected**.
4. **generic composition** — a mixed RAG re-rank under a **non-regis** `FieldMap`
   (`subject`/`predicate`/`effective_from`/…): outdated `$9` suppressed, current `$12` wins, an unrelated
   non-temporal passage passes through **in its original rank position**.
5. **oracle** — when `regis-entity-graph` is locatable (`REGIS_ENTITY_GRAPH` or a sibling checkout),
   `resolve()` == regis#20's `temporal_retrieve()` on the regis fixture (authoritative, suppressed,
   surviving, `is_superseded`). Self-skips cleanly otherwise; the vendored-fixture teeth still hold.

## Semantics

Retrieval-plane only: suppressing a candidate means *"do not surface as the current answer"*, **never**
*"this is false"*. Canonical supersession is owned by the ACR decision ledger / epistemic-edge promotion.

## Follow-up (tracked)

Per-surface wiring is filed as follow-up issues @mdheller: the **RAG router** (`tools/query-router`) applies
the filter before the answer card so a superseded chunk never reaches the user; **memory-mesh** applies it
on recall so stale memories are shadowed by their most-recent revision; and regis#20 delegates to this
shared core so the invariant has exactly one physical home.
