# text-to-sql (WO-A3, RAG GAP #79)

The **text-to-SQL query-construction** verb of the advanced-RAG reference architecture. Turns a
natural-language question into a **SAFE, parameterised** `SELECT` against a *declared* read-only
schema, and hard-rejects everything outside the safe subset with stable reason codes. Closes the
`GAP` verdict for element #1 (SQL construction) in the conformance matrix (#78), and replaces the
v0.1 stub the `query-router` (#77) emitted for `construction_verb="text-to-sql"`.

Consume-not-fork: the declared schema is the **memoryd `memories` table** verbatim
(`prophet-platform/apps/memoryd/src/memoryd/sqlite_store.py`) — no new DB is stood up; the fixture
recreates that exact DDL in an `:memory:` connection so constructed queries actually execute.

## Pieces

| File | Role |
|---|---|
| `sql_subset.py` | `validate_select(sql, schema)` (parse+validate a proposed string, read-only subset) **and** `build_sql(question, schema)` (NL→parameterised `SafeSelect`, re-validated before return). Stable reason codes; caps (`LIMIT_CAP`). |
| `fixtures/memories_fixture.py` | In-memory SQLite mirroring the memoryd `memories` schema + seeded rows (opened `query_only`). |
| `tests/conformance_test.py` | 29 checks, teeth both ways (constructed queries execute + return the expected rows; unsafe/out-of-schema strings rejected with the expected code). Run: `python3 tests/conformance_test.py`. |
| `query_sql.proto` | triRPC IDL for the `TextToSql.BuildSql` verb. |

## Safe subset (v0.1)

Accepted: `SELECT <cols|COUNT(*)|agg(col)> FROM <declared table> [WHERE ...] [GROUP BY col] LIMIT n`
— only declared columns/table, mandatory `LIMIT <= 1000`, user values bound as `?` params.

Rejected (stable code): `INSERT/UPDATE/DELETE` (`mutation-*`), `DROP/ALTER/CREATE/TRUNCATE` (`ddl-*`),
`PRAGMA/ATTACH/EXEC/CALL`, `UNION` (`union-unsupported`), stacked statements (`multiple-statements`),
SQL comments (`comment-unsupported`), out-of-schema table (`unknown-table`) / column
(`unknown-column`), missing/over-cap `LIMIT` (`limit-required`/`limit-cap`), and an NL question that
maps to no in-schema predicate (`no-mappable-intent` — fail-closed, never a blind full-scan).

**Injection is safe by construction:** user-supplied values are never interpolated into the SQL text;
they are bound parameters, and the emitted SQL is re-checked by `validate_select` before return. See
the injection teeth in the conformance suite.

## Wiring

Behind `query-router`'s `text-to-sql` verb: `router.construct_query(choice, question=...)` calls
`build_sql` and hands the store a `SafeSelect`. Path-filtered CI (`.github/workflows/text-to-sql.yml`,
and the `query-router.yml` paths) gates the suite so the contract cannot silently rot.

## Runtime (out of scope here — filed)

Live execution against a running memoryd/Postgres is a runtime concern (no live writes from this
contract). Tracked as a follow-up issue to @mdheller.

Refs #33, #78, #79.
