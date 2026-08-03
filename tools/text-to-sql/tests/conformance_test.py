"""text-to-SQL conformance — runnable with `python3 tests/conformance_test.py` (no pytest dep).

Teeth verified BOTH ways (ADR-0001 discipline), closing GAP #79:
  POSITIVE — NL questions build SAFE, parameterised SELECTs whose identifiers are all declared, whose
             user values are bound params (never interpolated), and which EXECUTE against a fixture
             mirroring the memoryd `memories` schema and return the expected rows.
  NEGATIVE — injection / mutation / DDL / stacked statements / out-of-schema table+column / missing or
             over-cap LIMIT / no-mappable-intent are all REJECTED with the expected stable code, and an
             injection payload provably lands in a BOUND PARAM (never in the emitted SQL text).
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
sys.path.insert(0, PKG)
sys.path.insert(0, os.path.join(PKG, "fixtures"))

from sql_subset import (  # noqa: E402
    MEMORIES_SCHEMA, SqlRejected, build_sql, validate_select,
)
from memories_fixture import make_conn  # noqa: E402

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


def expect_reject(name: str, fn, code: str) -> None:
    try:
        fn()
        check(name, False, f"expected reject {code}, but it succeeded")
    except SqlRejected as e:
        check(name, e.code == code, f"expected {code}, got {e.code}")


def main() -> int:
    conn = make_conn()

    # --- POSITIVE: aggregation question → COUNT(*), executes, returns the right total ---------------
    q = build_sql("how many memories are there")
    check("count question → COUNT(*), no WHERE", q.sql == "SELECT COUNT(*) FROM memories LIMIT 25",
          q.sql)
    (total,) = conn.execute(q.sql, q.params).fetchone()
    check("count(*) executes and returns all 6 fixture rows", total == 6, str(total))

    # --- POSITIVE: enum predicate (memory_class) parameterised + executes --------------------------
    q = build_sql("how many fact memories are there")
    check("enum predicate parameterised (value is a bound param, not in SQL)",
          "memory_class = ?" in q.sql and q.params == ["fact"], f"{q.sql} :: {q.params}")
    (facts,) = conn.execute(q.sql, q.params).fetchone()
    check("class=fact count executes → 2 fixture rows", facts == 2, str(facts))

    # --- POSITIVE: topical LIKE over the text column, value bound as %term% ------------------------
    q = build_sql("find memories about coastal erosion")
    check("topical question → LIKE ? over text_content, term is a bound param",
          "text_content LIKE ?" in q.sql and q.params == ["%coastal erosion%"], f"{q.sql} :: {q.params}")
    rows = conn.execute(q.sql, q.params).fetchall()
    check("LIKE query executes and finds the 2 'coastal erosion' rows (m1,m5)",
          len(rows) == 2, str(len(rows)))

    # --- POSITIVE: temporal range → parameterised created_at bound (never interpolated) ------------
    q = build_sql("find memories about erosion after 2021")
    check("temporal 'after 2021' → created_at >= ? bound param",
          "created_at >= ?" in q.sql and "2021-01-01" in q.params, f"{q.sql} :: {q.params}")
    rows = conn.execute(q.sql, q.params).fetchall()
    check("erosion-after-2021 executes → m3,m4,m5 (3 rows)", len(rows) == 3, str(len(rows)))

    # --- POSITIVE: GROUP BY a declared column executes ---------------------------------------------
    q = build_sql("count memories per memory_class")
    check("group-by declared column → GROUP BY memory_class",
          "GROUP BY memory_class" in q.sql, q.sql)
    grouped = dict(conn.execute(q.sql, q.params).fetchall())
    check("group-by executes → fact bucket has 2", grouped.get("fact") == 2, str(grouped))

    # --- POSITIVE: recall intent → bounded scan, mandatory LIMIT present ----------------------------
    q = build_sql("list recent memories", limit=10)
    check("recall intent → bounded SELECT * with LIMIT", q.sql == "SELECT * FROM memories LIMIT 10",
          q.sql)

    # --- TEETH: injection payload lands in a BOUND PARAM, never in the SQL text ---------------------
    payload = "'; DROP TABLE memories; --"
    q = build_sql(f"find memories about {payload}")
    check("injection payload is NOT present in the emitted SQL text",
          "DROP" not in q.sql.upper() and ";" not in q.sql, q.sql)
    check("injection payload IS carried in the bound LIKE parameter (not the SQL)",
          len(q.params) == 1 and "DROP TABLE memories" in q.params[0]
          and q.params[0].startswith("%") and q.params[0].endswith("%"), str(q.params))
    # and it executes harmlessly (matches nothing, table still intact)
    rows = conn.execute(q.sql, q.params).fetchall()
    check("injection query executes harmlessly (0 rows, table intact)",
          rows == [] and conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0] == 6, str(rows))

    # --- NEGATIVE: validate_select hard-rejects unsafe PROPOSED strings -----------------------------
    expect_reject("reject DELETE (mutation)", lambda: validate_select("DELETE FROM memories LIMIT 1"),
                  "mutation-delete")
    expect_reject("reject UPDATE (mutation)",
                  lambda: validate_select("UPDATE memories SET revoked=1 LIMIT 1"), "mutation-update")
    expect_reject("reject DROP (DDL)", lambda: validate_select("DROP TABLE memories"), "ddl-drop")
    expect_reject("reject stacked statements",
                  lambda: validate_select("SELECT * FROM memories LIMIT 1; DROP TABLE memories"),
                  "multiple-statements")
    expect_reject("reject SQL comment",
                  lambda: validate_select("SELECT * FROM memories -- drop\n LIMIT 1"),
                  "comment-unsupported")
    expect_reject("reject UNION (subset)",
                  lambda: validate_select("SELECT * FROM memories UNION SELECT * FROM memories LIMIT 1"),
                  "union-unsupported")
    expect_reject("reject non-SELECT",
                  lambda: validate_select("PRAGMA table_info(memories)"), "pragma-unsupported")
    expect_reject("reject out-of-schema table",
                  lambda: validate_select("SELECT * FROM users LIMIT 1"), "unknown-table")
    expect_reject("reject out-of-schema column in SELECT list",
                  lambda: validate_select("SELECT password FROM memories LIMIT 1"), "unknown-column")
    expect_reject("reject out-of-schema column in WHERE",
                  lambda: validate_select("SELECT * FROM memories WHERE ssn = 1 LIMIT 1"),
                  "unknown-column")
    expect_reject("reject missing LIMIT (mandatory cap)",
                  lambda: validate_select("SELECT * FROM memories"), "limit-required")
    expect_reject("reject over-cap LIMIT",
                  lambda: validate_select("SELECT * FROM memories LIMIT 99999"), "limit-cap")

    # --- NEGATIVE: build_sql fail-closed on unmappable + out-of-schema group-by ---------------------
    expect_reject("reject no-mappable-intent (no blind full-scan)",
                  lambda: build_sql("what is the meaning of life"), "no-mappable-intent")
    expect_reject("reject group-by over undeclared column",
                  lambda: build_sql("count memories per ssn"), "unknown-column")
    expect_reject("reject empty question", lambda: build_sql("   "), "empty")

    conn.close()
    print(f"\n{_passed} passed, {_failed} failed")
    return 1 if _failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
