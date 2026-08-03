"""Self-query constructor (NL → {semantic_query, metadata_filter}) for the vector self-query verb.

WO-A3 of ADR-0001 (Open Agent Continuum), closing the RAG-conformance GAP #80 (vector self-query).
Mirrors the `cypher-atomspace-gateway` shape: a *contract* layer that turns a natural-language query
into a residual semantic query PLUS a structured metadata filter over a DECLARED field schema, and
HARD-REJECTS filters over undeclared fields / unsupported operators with stable reason codes
(fail-closed — never a silent full-scan on a bad filter). Two independent teeth back the same caps:

  * `compile_filter(constraints, schema)` — validate+compile a PROPOSED MongoDB-style constraint set
    (`{field: {"$op": value}}`, the operator vocabulary of the AgenticaForge `MetadataFilter` fork,
    reused as REFERENCE ONLY) into a **Qdrant-acceptable** filter `{must:[...], must_not:[...]}`
    (`match`/`range`/`is_empty`, exactly the shape memoryd's `qdrant_index.py` sends). Rejects
    undeclared fields, unsupported operators, and type-mismatched operands.
  * `build_self_query(question, schema)` — the v0.1 NL→filter constructor. Extracts implied
    constraints (`memory_class` enum, temporal `after/before/in <year>`, `tagged <t>`) into the
    MongoDB-style form, compiles them through `compile_filter`, and returns
    `{semantic_query, metadata_filter}` where `semantic_query` is the NL with the filter phrases
    stripped. Ambiguous / unrecognised phrasing is passed through CLEANLY as pure semantic query
    (no filter, no silent wrong constraint) — but a phrase that explicitly names an UNDECLARED field
    is rejected. The LLM extractor is the documented seam that replaces the rule extraction while
    keeping this fail-closed contract.

Consume-not-fork: the emitted filter shape is what the shared Qdrant substrate accepts
(`prophet-platform/apps/memoryd/src/memoryd/qdrant_index.py`, collection `memorymesh-recall`); the
fork's `$eq/$gt/$in/$exists` operator semantics are the reference, not a dependency.

Run the teeth:  python3 tests/conformance_test.py
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


class FilterRejected(Exception):
    """Raised when a proposed filter is outside the safe subset. `.code` is a stable reason code."""

    def __init__(self, code: str, message: str):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


# --- declared field schema (the allowlist; a field not here is never filtered on) --------------------
@dataclass(frozen=True)
class Field:
    name: str
    kind: str  # "keyword" | "int" | "float" | "enum" | "date"
    enum: tuple[str, ...] = ()          # allowed values when kind == "enum"
    is_list: bool = False               # payload value is a list (e.g. tags) → membership semantics


@dataclass(frozen=True)
class FieldSchema:
    fields: tuple[Field, ...]

    def field(self, name: str) -> Field | None:
        for f in self.fields:
            if f.name == name:
                return f
        return None

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(f.name for f in self.fields)


# memoryd `memorymesh-recall` payload fields (verbatim from qdrant_index.py) + a declared date field.
MEMORYMESH_SCHEMA = FieldSchema(fields=(
    Field("memory_class", "enum",
          enum=("interaction", "fact", "preference", "decision", "summary", "scratch")),
    Field("tags", "keyword", is_list=True),
    Field("user_id", "keyword"),
    Field("agent_id", "keyword"),
    Field("workload_id", "keyword"),
    Field("workspace_id", "keyword"),
    Field("source_interface", "keyword"),
    Field("created_at", "date"),
))

# A second declared schema for a document/corpus collection ("papers on X after 2020" in the issue).
CORPUS_SCHEMA = FieldSchema(fields=(
    Field("domain", "keyword"),
    Field("author", "keyword"),
    Field("tags", "keyword", is_list=True),
    Field("year", "int"),
))


# --- operator subset (the fork's vocabulary; reference-only) → Qdrant conditions ---------------------
_SUPPORTED_OPS = {"$eq", "$ne", "$gt", "$gte", "$lt", "$lte", "$in", "$nin", "$exists"}
_RANGE_OP = {"$gt": "gt", "$gte": "gte", "$lt": "lt", "$lte": "lte"}


def _check_type(field: Field, value, op: str) -> None:
    if field.kind in ("int", "float", "date") and op in ("$gt", "$gte", "$lt", "$lte"):
        if field.kind in ("int",) and not isinstance(value, int):
            raise FilterRejected("operand-type", f"{field.name} {op} expects an int, got {value!r}")
        if field.kind == "float" and not isinstance(value, (int, float)):
            raise FilterRejected("operand-type", f"{field.name} {op} expects a number, got {value!r}")
        if field.kind == "date" and not isinstance(value, str):
            raise FilterRejected("operand-type", f"{field.name} {op} expects a date string, got {value!r}")
    if op in ("$in", "$nin") and not isinstance(value, (list, tuple)):
        raise FilterRejected("operand-type", f"{field.name} {op} expects a list, got {value!r}")
    if field.kind == "enum" and op in ("$eq", "$ne"):
        if value not in field.enum:
            raise FilterRejected("enum-value",
                                 f"{value!r} is not a declared value of enum '{field.name}'")
    if field.kind == "enum" and op in ("$in", "$nin"):
        bad = [v for v in value if v not in field.enum]
        if bad:
            raise FilterRejected("enum-value",
                                 f"{bad!r} not declared values of enum '{field.name}'")


def _condition(field: Field, op: str, value) -> tuple[str, dict]:
    """Return (bucket, condition) where bucket is 'must' or 'must_not'. Qdrant-shaped."""
    key = field.name
    if op == "$eq":
        return "must", {"key": key, "match": {"value": value}}
    if op == "$ne":
        return "must_not", {"key": key, "match": {"value": value}}
    if op == "$in":
        return "must", {"key": key, "match": {"any": list(value)}}
    if op == "$nin":
        return "must_not", {"key": key, "match": {"any": list(value)}}
    if op in _RANGE_OP:
        return "must", {"key": key, "range": {_RANGE_OP[op]: value}}
    if op == "$exists":
        # Qdrant models "field is empty"; exists=True ⇒ NOT empty (must_not is_empty)
        return ("must_not" if value else "must"), {"is_empty": {"key": key}}
    raise FilterRejected("unsupported-operator", f"operator '{op}' is not supported")


@dataclass
class SelfQuery:
    semantic_query: str
    metadata_filter: dict          # Qdrant filter: {"must":[...], "must_not":[...]} (empty ⇒ absent)
    plan: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"semantic_query": self.semantic_query, "metadata_filter": self.metadata_filter,
                "plan": self.plan}


def compile_filter(constraints: dict, schema: FieldSchema = MEMORYMESH_SCHEMA) -> dict:
    """Validate + compile a MongoDB-style constraint set to a Qdrant filter. Fail-closed.

    `constraints` is `{field: value}` (implicit `$eq`) or `{field: {"$op": value, ...}}`. Every field
    must be declared and every operator supported; range operators over one field merge into a single
    `range` condition. Returns `{"must":[...], "must_not":[...]}` with empty buckets omitted.
    """
    must: list[dict] = []
    must_not: list[dict] = []
    for fname, spec in constraints.items():
        fld = schema.field(fname)
        if fld is None:
            raise FilterRejected("unknown-field",
                                 f"field '{fname}' is not declared (declared: {list(schema.names)})")
        ops = spec if isinstance(spec, dict) and any(k.startswith("$") for k in spec) else {"$eq": spec}
        range_cond: dict | None = None
        for op, value in ops.items():
            if op not in _SUPPORTED_OPS:
                raise FilterRejected("unsupported-operator",
                                     f"operator '{op}' not in supported subset {sorted(_SUPPORTED_OPS)}")
            _check_type(fld, value, op)
            if op in _RANGE_OP:
                range_cond = range_cond or {"key": fname, "range": {}}
                range_cond["range"][_RANGE_OP[op]] = value
                continue
            bucket, cond = _condition(fld, op, value)
            (must if bucket == "must" else must_not).append(cond)
        if range_cond:
            must.append(range_cond)
    out: dict = {}
    if must:
        out["must"] = must
    if must_not:
        out["must_not"] = must_not
    return out


# --- NL→filter extraction (v0.1 rules; LLM extractor is the documented seam) -------------------------
_AFTER = re.compile(r"\b(?:after|since)\s+(\d{4})\b", re.IGNORECASE)
_BEFORE = re.compile(r"\bbefore\s+(\d{4})\b", re.IGNORECASE)
_IN_YEAR = re.compile(r"\b(?:in|from|during)\s+(\d{4})\b", re.IGNORECASE)
_TAGGED = re.compile(r"\b(?:tagged|with tag|tag[:=])\s+([a-z0-9_\-]+)", re.IGNORECASE)
_DOMAIN = re.compile(r"\bin (?:the )?domain\s+([a-z0-9_\-]+)", re.IGNORECASE)
# an explicit "field:value" / "field = value" mention lets a user name a field directly
_EXPLICIT_FIELD = re.compile(r"\b([a-z_][a-z0-9_]*)\s*(?::|=)\s*([a-z0-9_\-]+)", re.IGNORECASE)


def _date_field(schema: FieldSchema) -> Field | None:
    for f in schema.fields:
        if f.kind == "date":
            return f
    return None


def _year_field(schema: FieldSchema) -> Field | None:
    for f in schema.fields:
        if f.kind == "int" and f.name in ("year", "published_year"):
            return f
    return None


def _enum_field_value(schema: FieldSchema, qlc: str) -> tuple[str, str] | None:
    for f in schema.fields:
        if f.kind != "enum":
            continue
        for v in f.enum:
            if re.search(rf"\b{re.escape(v)}\b", qlc):
                return f.name, v
    return None


def build_self_query(question: str, schema: FieldSchema = MEMORYMESH_SCHEMA) -> SelfQuery:
    """NL question → {semantic_query, metadata_filter}. Recognised filter phrases become a compiled,
    schema-validated Qdrant filter; the matched phrases are stripped from the residual semantic query.
    Unrecognised phrasing passes through cleanly (semantic-only). An explicit `field:value` naming an
    UNDECLARED field is rejected (fail-closed)."""
    if not question or not question.strip():
        raise FilterRejected("empty", "empty question")
    q = question.strip()
    qlc = " " + q.lower() + " "
    constraints: dict = {}
    plan: list[str] = []
    consumed_spans: list[tuple[int, int]] = []

    def consume(m):
        consumed_spans.append(m.span())

    # temporal → range on the declared date field (as a date string) or int year field
    df, yf = _date_field(schema), _year_field(schema)
    ma, mb, mi = _AFTER.search(q), _BEFORE.search(q), _IN_YEAR.search(q)
    if df:
        rng: dict = {}
        if ma:
            rng["$gte"] = f"{ma.group(1)}-01-01"; consume(ma); plan.append(f"{df.name} $gte {ma.group(1)}")
        elif mi:
            rng["$gte"] = f"{mi.group(1)}-01-01"; rng["$lt"] = f"{int(mi.group(1))+1}-01-01"
            consume(mi); plan.append(f"{df.name} in {mi.group(1)}")
        if mb:
            rng["$lt"] = f"{mb.group(1)}-01-01"; consume(mb); plan.append(f"{df.name} $lt {mb.group(1)}")
        if rng:
            constraints[df.name] = rng
    elif yf:
        rng = {}
        if ma:
            rng["$gt"] = int(ma.group(1)); consume(ma); plan.append(f"{yf.name} $gt {ma.group(1)}")
        elif mi:
            rng["$eq"] = int(mi.group(1)); consume(mi); plan.append(f"{yf.name} == {mi.group(1)}")
        if mb:
            rng["$lt"] = int(mb.group(1)); consume(mb); plan.append(f"{yf.name} $lt {mb.group(1)}")
        if rng:
            constraints[yf.name] = rng

    # enum (e.g. memory_class fact/decision/...)
    ev = _enum_field_value(schema, qlc)
    if ev:
        constraints[ev[0]] = ev[1]
        plan.append(f"{ev[0]} == {ev[1]}")
        m_en = re.search(rf"\b{re.escape(ev[1])}\b", q, re.IGNORECASE)
        if m_en:
            consume(m_en)

    # tags → membership ($in with a single value)
    mt = _TAGGED.search(q)
    if mt and schema.field("tags"):
        constraints["tags"] = {"$in": [mt.group(1).lower()]}
        consume(mt); plan.append(f"tags $in [{mt.group(1).lower()}]")

    # domain
    md = _DOMAIN.search(q)
    if md and schema.field("domain"):
        constraints["domain"] = md.group(1).lower()
        consume(md); plan.append(f"domain == {md.group(1).lower()}")

    # explicit field:value — the fail-closed teeth for an UNDECLARED field reference
    for m in _EXPLICIT_FIELD.finditer(q):
        fname, val = m.group(1).lower(), m.group(2)
        if fname in ("http", "https"):   # ignore urls
            continue
        if schema.field(fname) is None:
            raise FilterRejected("unknown-field",
                                 f"query names undeclared field '{fname}' (declared: {list(schema.names)})")
        if fname not in constraints:
            constraints[fname] = val
            consume(m); plan.append(f"{fname} == {val} (explicit)")

    metadata_filter = compile_filter(constraints, schema) if constraints else {}

    # residual semantic query: strip the consumed filter spans, collapse whitespace + dangling preps
    residual = q
    for (s, e) in sorted(consumed_spans, reverse=True):
        residual = residual[:s] + residual[e:]
    residual = re.sub(r"\s+", " ", residual).strip()
    residual = re.sub(r"\b(?:with|in|the|domain|tagged|from)\b\s*$", "", residual,
                      flags=re.IGNORECASE).strip(" ,.")
    if not plan:
        plan.append("no filter phrase recognised → semantic-only passthrough")

    return SelfQuery(semantic_query=residual or q, metadata_filter=metadata_filter, plan=plan)
