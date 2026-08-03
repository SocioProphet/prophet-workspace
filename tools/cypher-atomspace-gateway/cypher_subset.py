"""Cypher-subset parser + validator (safe subset v0.1) for the Cypher -> AtomSpace/HellGraph gateway.

WO-A of ADR-0001 (Open Agent Continuum). This is the *contract* layer: it accepts ONLY the safe
Cypher subset an agent (Sherlock Scout / Loom) is allowed to run against the canonical graph, and
HARD-REJECTS everything else. The caps here are the gateway half of the "enforced, not documented"
rule (AC-4): the same caps are re-checked by Sentinel policy, so a bypass of one is caught by the other.

Accepted (v0.1), targeting CSKG usage:
    MATCH (h:Concept {form:$lemma})-[:CSKG*1..2]->(t) RETURN t.form LIMIT 25
  - a single node-label + property match as the anchor
  - one relationship (type, optional {relation: ...} filter), left-to-right
  - bounded variable-length hops  *MIN..MAX  (MAX <= HOP_CAP)
  - RETURN of node properties
  - mandatory LIMIT (<= LIMIT_CAP)

Rejected (hard-fail with a reason code):
  - mutation:            CREATE / DELETE / SET / MERGE / REMOVE
  - procedures:          CALL ...
  - unbounded hops:      -[:R*]->  or  -[:R*2..]->  or hops > HOP_CAP
  - missing / oversized LIMIT
  - multiple MATCH clauses, WHERE, UNION, WITH (deferred until a cost model exists, ADR-0001 sec.9/5)
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# --- Sentinel caps (the gateway copy; policy holds the authoritative copy) ---------------------------
HOP_CAP = 2            # max variable-length hops an agent query may traverse
LIMIT_CAP = 100        # max rows an agent query may request
DEFAULT_LIMIT = 25


class CypherRejected(Exception):
    """Raised when a query is outside the safe subset. `.code` is a stable reason code."""

    def __init__(self, code: str, message: str):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


# Case-insensitive tokens that are never allowed in an agent query.
_FORBIDDEN = {
    "CREATE": "mutation-create", "DELETE": "mutation-delete", "SET": "mutation-set",
    "MERGE": "mutation-merge", "REMOVE": "mutation-remove", "CALL": "procedure-call",
    "WHERE": "where-unsupported", "UNION": "union-unsupported", "WITH": "with-unsupported",
    "LOAD": "load-unsupported", "FOREACH": "foreach-unsupported",
}

# (h:Label {prop:$param|"literal"}) -[:TYPE *min..max {relation:...}]-> (t)  RETURN t.prop  LIMIT n
_ANCHOR = re.compile(
    r"\(\s*(?P<hvar>\w+)\s*:\s*(?P<hlabel>\w+)\s*\{\s*(?P<hprop>\w+)\s*:\s*(?P<hval>\$\w+|\"[^\"]*\"|'[^']*')\s*\}\s*\)"
)
_REL = re.compile(
    r"-\s*\[\s*:\s*(?P<rtype>\w+)\s*(?:\*\s*(?P<hmin>\d+)\s*\.\.\s*(?P<hmax>\d+)\s*)?"
    r"(?:\{\s*relation\s*:\s*(?P<relf>\$\w+|\"[^\"]*\"|'[^']*')\s*\}\s*)?\]\s*->"
)
_TAIL = re.compile(r"\(\s*(?P<tvar>\w+)\s*\)")
_RETURN = re.compile(r"\bRETURN\s+(?P<rvar>\w+)\.(?P<rprop>\w+)", re.IGNORECASE)
_LIMIT = re.compile(r"\bLIMIT\s+(?P<limit>\d+)", re.IGNORECASE)
_UNBOUNDED_STAR = re.compile(r"\*\s*(?!\d+\s*\.\.\s*\d+)")  # a '*' not immediately followed by min..max


@dataclass
class ParsedQuery:
    """A validated, safe query reduced to the fields the translator needs."""
    anchor_var: str
    anchor_label: str
    anchor_prop: str
    anchor_value: str          # param name ($lemma) or a literal (quotes stripped)
    anchor_is_param: bool
    rel_type: str
    hop_min: int
    hop_max: int
    relation_filter: str | None
    relation_is_param: bool
    tail_var: str
    return_var: str
    return_prop: str
    limit: int
    plan: list[str] = field(default_factory=list)


def _strip_quotes(v: str) -> tuple[str, bool]:
    """Return (value, is_param). Params start with '$'; literals get their quotes stripped."""
    if v.startswith("$"):
        return v[1:], True
    return v.strip("\"'"), False


def parse(query: str) -> ParsedQuery:
    """Parse+validate a query against the safe subset. Raises CypherRejected on any violation."""
    if not query or not query.strip():
        raise CypherRejected("empty", "empty query")
    q = " ".join(query.strip().split())  # normalise whitespace

    # 1) forbidden keywords (mutation / procedures / unsupported clauses) — check as whole words
    for kw, code in _FORBIDDEN.items():
        if re.search(rf"\b{kw}\b", q, re.IGNORECASE):
            raise CypherRejected(code, f"'{kw}' is not permitted in an agent query")

    # 2) exactly one MATCH
    if len(re.findall(r"\bMATCH\b", q, re.IGNORECASE)) != 1:
        raise CypherRejected("match-shape", "exactly one MATCH clause is required")

    # 3) structural match: anchor -> rel -> tail
    a, r, t = _ANCHOR.search(q), _REL.search(q), None
    if not a:
        raise CypherRejected("anchor-shape", "expected an anchor node (var:Label {prop:value})")
    if not r:
        # distinguish an unbounded '*' from a plain missing relationship, for a precise reason code
        if _UNBOUNDED_STAR.search(q):
            raise CypherRejected("unbounded-hops", "variable-length hops must be bounded as *min..max")
        raise CypherRejected("rel-shape", "expected one bounded relationship -[:TYPE*min..max]->")
    t = _TAIL.search(q, r.end())
    if not t:
        raise CypherRejected("tail-shape", "expected a tail node after the relationship")

    # 4) hop bounds + cap
    hmin = int(r.group("hmin")) if r.group("hmin") else 1
    hmax = int(r.group("hmax")) if r.group("hmax") else 1
    if hmax < hmin or hmin < 1:
        raise CypherRejected("hop-range", f"invalid hop range {hmin}..{hmax}")
    if hmax > HOP_CAP:
        raise CypherRejected("hop-cap", f"hop bound {hmax} exceeds cap {HOP_CAP}")

    # 5) RETURN <var>.<prop>
    ret = _RETURN.search(q)
    if not ret:
        raise CypherRejected("return-shape", "expected RETURN <var>.<prop>")

    # 6) mandatory LIMIT within cap
    lim = _LIMIT.search(q)
    if not lim:
        raise CypherRejected("limit-required", f"a LIMIT is mandatory (<= {LIMIT_CAP})")
    limit = int(lim.group("limit"))
    if limit < 1 or limit > LIMIT_CAP:
        raise CypherRejected("limit-cap", f"LIMIT {limit} outside 1..{LIMIT_CAP}")

    aval, ais_param = _strip_quotes(a.group("hval"))
    relf, rel_is_param = (None, False)
    if r.group("relf"):
        relf, rel_is_param = _strip_quotes(r.group("relf"))

    return ParsedQuery(
        anchor_var=a.group("hvar"), anchor_label=a.group("hlabel"),
        anchor_prop=a.group("hprop"), anchor_value=aval, anchor_is_param=ais_param,
        rel_type=r.group("rtype"), hop_min=hmin, hop_max=hmax,
        relation_filter=relf, relation_is_param=rel_is_param,
        tail_var=t.group("tvar"), return_var=ret.group("rvar"), return_prop=ret.group("rprop"),
        limit=limit,
        plan=[f"anchor {a.group('hlabel')}.{a.group('hprop')}={aval}",
              f"expand :{r.group('rtype')} *{hmin}..{hmax}" + (f" {{relation:{relf}}}" if relf else ""),
              f"return {ret.group('rvar')}.{ret.group('rprop')} limit {limit}"],
    )
