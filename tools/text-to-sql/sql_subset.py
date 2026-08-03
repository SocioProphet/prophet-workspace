"""SQL-subset validator + NL→SQL constructor (safe subset v0.1) for the text-to-SQL query verb.

WO-A3 of ADR-0001 (Open Agent Continuum), closing the RAG-conformance GAP #79 (text-to-SQL).
Mirrors the `cypher-atomspace-gateway` shape exactly: a *contract* layer that accepts ONLY a safe,
read-only SQL subset an agent may run against a declared relational schema, and HARD-REJECTS
everything else with stable reason codes. Two independent teeth back the same caps:

  * `validate_select(sql, schema)` — parse+validate a PROPOSED SQL string. SELECT-only, single
    statement, only declared tables/columns, mandatory LIMIT within cap. Rejects mutation/DDL,
    stacked statements, comments, and out-of-schema identifiers. This is the "the caller (or an LLM
    seam) proposed a query, prove it is safe before it ever reaches a cursor" half.
  * `build_sql(question, schema)` — the v0.1 NL→SQL constructor. Turns a natural-language question
    into a **parameterised** SELECT (`?` placeholders + a params list) whose identifiers come ONLY
    from the declared schema allowlist and whose user-supplied VALUES are NEVER interpolated into the
    SQL text — they are bound parameters. So an injection payload lands in a bound value, never in
    the query, and the constructed SQL is itself re-checked by `validate_select` before return
    (safe-by-construction, verified — not asserted). The LLM router is the documented seam that can
    replace the rule scoring while keeping this fail-closed contract, exactly as `cypher_subset`'s
    regex-v0.1-with-a-cost-model-seam.

Target schema (consume-not-fork): the memoryd `memories` table
(`prophet-platform/apps/memoryd/src/memoryd/sqlite_store.py`) — no new DB is stood up; the fixture
mirrors that exact schema.

Run the teeth:  python3 tests/conformance_test.py
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


# --- caps (the constructor copy; a live executor would re-check independently, AC-4) -----------------
LIMIT_CAP = 1000        # max rows a constructed/validated query may request
DEFAULT_LIMIT = 25


class SqlRejected(Exception):
    """Raised when a query is outside the safe subset. `.code` is a stable reason code."""

    def __init__(self, code: str, message: str):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


# --- declared schema (the allowlist; identifiers not in here are never emitted or accepted) ----------
@dataclass(frozen=True)
class Column:
    name: str
    kind: str  # "text" | "int" | "enum" | "timestamp"
    enum: tuple[str, ...] = ()          # allowed literal values when kind == "enum"
    aggregatable: bool = True           # may appear in GROUP BY / ORDER BY


@dataclass(frozen=True)
class TableSchema:
    """A single declared table. Only these columns may ever appear in a constructed/validated query."""
    table: str
    columns: tuple[Column, ...]

    def column(self, name: str) -> Column | None:
        for c in self.columns:
            if c.name == name:
                return c
        return None

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(c.name for c in self.columns)


# The memoryd `memories` table, verbatim from sqlite_store.py (consume-not-fork).
MEMORIES_SCHEMA = TableSchema(
    table="memories",
    columns=(
        Column("memory_id", "text"),
        Column("text_content", "text"),
        Column("memory_class", "enum",
               enum=("interaction", "fact", "preference", "decision", "summary", "scratch")),
        Column("tags_json", "text"),
        Column("metadata_json", "text"),
        Column("event_id", "text"),
        Column("created_at", "timestamp"),
        Column("revoked", "int"),
    ),
)


# --- forbidden tokens (mutation / DDL / procedures / stacking) ---------------------------------------
_FORBIDDEN = {
    "INSERT": "mutation-insert", "UPDATE": "mutation-update", "DELETE": "mutation-delete",
    "DROP": "ddl-drop", "ALTER": "ddl-alter", "CREATE": "ddl-create", "TRUNCATE": "ddl-truncate",
    "REPLACE": "mutation-replace", "MERGE": "mutation-merge", "GRANT": "priv-grant",
    "REVOKE": "priv-revoke", "ATTACH": "attach-unsupported", "PRAGMA": "pragma-unsupported",
    "VACUUM": "vacuum-unsupported", "UNION": "union-unsupported", "INTO": "into-unsupported",
    "EXEC": "exec-unsupported", "EXECUTE": "exec-unsupported", "CALL": "call-unsupported",
}

_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_SELECT_RE = re.compile(r"^\s*SELECT\s+(?P<cols>.+?)\s+FROM\s+(?P<rest>.+)$", re.IGNORECASE | re.DOTALL)
_LIMIT_RE = re.compile(r"\bLIMIT\s+(?P<limit>\d+)\s*$", re.IGNORECASE)
# a select-column item: COUNT(*), a bare column, or COUNT(col) / an aggregate over a column
_AGG_RE = re.compile(r"^(?P<fn>COUNT|SUM|AVG|MIN|MAX)\s*\(\s*(?P<arg>\*|[A-Za-z_][A-Za-z0-9_]*)\s*\)$",
                     re.IGNORECASE)


@dataclass
class SafeSelect:
    """A validated, safe, parameterised SELECT ready to hand to a read-only cursor."""
    sql: str
    params: list = field(default_factory=list)
    table: str = ""
    plan: list[str] = field(default_factory=list)


def _reject_comments_and_stacking(q: str) -> None:
    if "--" in q or "/*" in q or "*/" in q or "#" in q:
        raise SqlRejected("comment-unsupported", "SQL comments are not permitted")
    # a trailing ';' is tolerated and stripped by callers; an interior ';' means stacked statements
    if ";" in q.rstrip().rstrip(";"):
        raise SqlRejected("multiple-statements", "only a single statement is permitted")


def validate_select(sql: str, schema: TableSchema = MEMORIES_SCHEMA) -> SafeSelect:
    """Parse+validate a PROPOSED SQL string against the safe read-only subset.

    Accepts: `SELECT <cols|COUNT(*)|agg(col)> FROM <table> [WHERE ...] [GROUP BY col] [ORDER BY col
    [ASC|DESC]] LIMIT n`, where every identifier is a declared column/table and LIMIT ≤ cap.
    Rejects everything else with a stable reason code. Does not bind params (a validator, not a
    constructor) — `build_sql` produces the parameterised form.
    """
    if not sql or not sql.strip():
        raise SqlRejected("empty", "empty query")
    q = " ".join(sql.strip().split())
    _reject_comments_and_stacking(q)
    q = q.rstrip(";").strip()

    # 1) forbidden keywords (mutation / DDL / stacking / procedures) as whole words
    for kw, code in _FORBIDDEN.items():
        if re.search(rf"\b{kw}\b", q, re.IGNORECASE):
            raise SqlRejected(code, f"'{kw}' is not permitted in a read-only query")

    # 2) must be a single SELECT
    if not re.match(r"^\s*SELECT\b", q, re.IGNORECASE):
        raise SqlRejected("not-select", "only SELECT statements are permitted")
    m = _SELECT_RE.match(q)
    if not m:
        raise SqlRejected("select-shape", "expected SELECT <cols> FROM <table> ... LIMIT n")

    # 3) FROM <declared table>
    rest = m.group("rest")
    from_tok = _IDENT.match(rest)
    if not from_tok or from_tok.group(0) != schema.table:
        got = from_tok.group(0) if from_tok else "?"
        raise SqlRejected("unknown-table", f"table '{got}' is not the declared table '{schema.table}'")

    # 4) mandatory LIMIT within cap
    lim = _LIMIT_RE.search(q)
    if not lim:
        raise SqlRejected("limit-required", f"a trailing LIMIT is mandatory (<= {LIMIT_CAP})")
    limit = int(lim.group("limit"))
    if limit < 1 or limit > LIMIT_CAP:
        raise SqlRejected("limit-cap", f"LIMIT {limit} outside 1..{LIMIT_CAP}")

    # 5) SELECT list: only COUNT(*), declared columns, or agg(declared column)
    for item in (c.strip() for c in m.group("cols").split(",")):
        agg = _AGG_RE.match(item)
        if agg:
            arg = agg.group("arg")
            if arg != "*" and schema.column(arg) is None:
                raise SqlRejected("unknown-column", f"'{arg}' is not a declared column")
            continue
        if item == "*":
            continue
        if schema.column(item) is None:
            raise SqlRejected("unknown-column", f"select item '{item}' is not a declared column")

    # 6) every remaining identifier that is not a SQL keyword / placeholder must be a declared column
    _KEYWORDS = {"select", "from", "where", "group", "by", "order", "limit", "and", "or", "asc",
                 "desc", "like", "count", "sum", "avg", "min", "max", "as", schema.table.lower()}
    for ident in _IDENT.findall(q):
        low = ident.lower()
        if low in _KEYWORDS:
            continue
        if schema.column(ident) is None:
            raise SqlRejected("unknown-column", f"identifier '{ident}' is not a declared column")

    return SafeSelect(sql=q if lim else q, params=[], table=schema.table,
                      plan=[f"validated SELECT over {schema.table}", f"limit {limit}"])


# --- NL→SQL constructor (v0.1 rule router; LLM router is the documented seam) ------------------------
_COUNT_SIGNALS = ("how many", "count", "number of", "how much", "total number")
_AGG_SIGNALS = {"sum of": "SUM", "average": "AVG", "avg ": "AVG"}
_GROUP_RE = re.compile(r"\b(?:per|by|grouped by|group by)\s+([a-z_]+)", re.IGNORECASE)
# "about X" / "mentioning X" / "containing X" → a LIKE over the text column
_ABOUT_RE = re.compile(r"\b(?:about|mentioning|containing|regarding|on the topic of)\s+(.+?)"
                       r"(?:\s+(?:from|after|before|since|per|by|group|order|limit|in\s+\d{4})\b|$)",
                       re.IGNORECASE)
_YEAR_AFTER = re.compile(r"\b(?:after|since)\s+(\d{4})\b", re.IGNORECASE)
_YEAR_BEFORE = re.compile(r"\bbefore\s+(\d{4})\b", re.IGNORECASE)
_YEAR_IN = re.compile(r"\b(?:in|from|during)\s+(\d{4})\b", re.IGNORECASE)


def _text_column(schema: TableSchema) -> str | None:
    for c in schema.columns:
        if c.kind == "text" and c.name in ("text_content", "content", "text", "body"):
            return c.name
    return None


def _timestamp_column(schema: TableSchema) -> str | None:
    for c in schema.columns:
        if c.kind == "timestamp":
            return c.name
    return None


def _enum_column_for(schema: TableSchema, question_lc: str) -> tuple[str, str] | None:
    """If the question names a declared enum value, return (column, value)."""
    for c in schema.columns:
        if c.kind != "enum":
            continue
        for v in c.enum:
            if re.search(rf"\b{re.escape(v)}\b", question_lc):
                return c.name, v
    return None


def build_sql(question: str, schema: TableSchema = MEMORIES_SCHEMA,
              limit: int = DEFAULT_LIMIT) -> SafeSelect:
    """NL question → a SAFE, parameterised SELECT over the declared schema.

    Identifiers (table/columns) come ONLY from `schema`; user-supplied values are bound as `?`
    parameters and NEVER interpolated. The result is re-validated by `validate_select` before return.
    Fail-closed: a question that maps to no in-schema column/predicate raises SqlRejected rather than
    emitting a blind `SELECT *` guess is avoided — a bare recall (`SELECT * ... LIMIT n`) is only
    emitted when the question has a clear recall intent and no unresolved out-of-schema reference.
    """
    if not question or not question.strip():
        raise SqlRejected("empty", "empty question")
    if limit < 1 or limit > LIMIT_CAP:
        raise SqlRejected("limit-cap", f"requested limit {limit} outside 1..{LIMIT_CAP}")
    qlc = " " + question.lower().strip() + " "
    plan: list[str] = []
    params: list = []
    where: list[str] = []

    # SELECT list: count / aggregate / recall
    select_expr = "*"
    if any(s in qlc for s in _COUNT_SIGNALS):
        select_expr = "COUNT(*)"
        plan.append("intent=count → COUNT(*)")

    # GROUP BY <declared column>
    group_col = None
    gm = _GROUP_RE.search(question)
    if gm:
        cand = gm.group(1).lower()
        col = schema.column(cand)
        if col is None:
            raise SqlRejected("unknown-column", f"group-by column '{cand}' is not a declared column")
        group_col = col.name
        if select_expr in ("*", "COUNT(*)"):
            select_expr = f"{group_col}, COUNT(*)"
        plan.append(f"group by {group_col}")

    # enum predicate (e.g. memory_class fact/decision/...)
    enum_hit = _enum_column_for(schema, qlc)
    if enum_hit:
        col, val = enum_hit
        where.append(f"{col} = ?")
        params.append(val)
        plan.append(f"{col} = <param:{val}>")

    # temporal predicate → range on the declared timestamp column (values are PARAMS)
    ts = _timestamp_column(schema)
    if ts:
        ma, mb, mi = _YEAR_AFTER.search(question), _YEAR_BEFORE.search(question), _YEAR_IN.search(question)
        if ma:
            where.append(f"{ts} >= ?"); params.append(f"{ma.group(1)}-01-01")
            plan.append(f"{ts} >= <param>")
        elif mi:
            where.append(f"{ts} >= ?"); params.append(f"{mi.group(1)}-01-01")
            where.append(f"{ts} < ?"); params.append(f"{int(mi.group(1)) + 1}-01-01")
            plan.append(f"{ts} in <param year>")
        if mb:
            where.append(f"{ts} < ?"); params.append(f"{mb.group(1)}-01-01")
            plan.append(f"{ts} < <param>")

    # topical predicate → LIKE over the declared text column (value is a PARAM, never interpolated)
    txt = _text_column(schema)
    am = _ABOUT_RE.search(question)
    if am and txt:
        term = am.group(1).strip().strip("\"'").rstrip("?.! ")
        if term:
            where.append(f"{txt} LIKE ?")
            params.append(f"%{term}%")
            plan.append(f"{txt} LIKE <param>")

    # fail-closed: no predicate, no count, no group → require an explicit recall verb before a bare scan
    _RECALL = ("list", "show", "find", "recent", "latest", "all ", "get ", "give me", "recall",
               "what are", "which")
    if not where and select_expr == "*" and group_col is None:
        if not any(s in qlc for s in _RECALL):
            raise SqlRejected("no-mappable-intent",
                              "question maps to no in-schema predicate/aggregate (fail-closed, "
                              "not a blind full-scan)")
        plan.append("recall intent → bounded scan")

    sql = f"SELECT {select_expr} FROM {schema.table}"
    if where:
        sql += " WHERE " + " AND ".join(where)
    if group_col:
        sql += f" GROUP BY {group_col}"
    sql += f" LIMIT {limit}"

    # safe-by-construction, VERIFIED: the emitted SQL must itself pass the read-only validator
    validate_select(sql, schema)
    return SafeSelect(sql=sql, params=params, table=schema.table, plan=plan)
