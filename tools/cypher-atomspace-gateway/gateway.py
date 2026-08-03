"""Graph.QueryCypher — the triRPC gateway verb (WO-A of ADR-0001).

Flow:  parse+validate (safe subset)  ->  Sentinel re-check (independent caps)  ->  bind params
       ->  translate to a substrate expand  ->  execute via a HellGraph-compatible adapter  ->  rows+plan

The Sentinel re-check is deliberately a SEPARATE enforcement of the same caps as cypher_subset:
AC-4 of ADR-0001 says the caps are enforced at the gateway *and* in policy, so bypassing one is
caught by the other. Here Sentinel is a distinct code path that never trusts the parser's numbers.
"""
from __future__ import annotations

from dataclasses import dataclass

from adapter import GraphAdapter, Hit
from cypher_subset import HOP_CAP, LIMIT_CAP, CypherRejected, ParsedQuery, parse


class SentinelDenied(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


def sentinel_check(pq: ParsedQuery) -> None:
    """Independent policy enforcement of the hop/limit caps (AC-4). Never trusts the parser."""
    if pq.hop_max > HOP_CAP or pq.hop_min < 1 or pq.hop_max < pq.hop_min:
        raise SentinelDenied("policy-hop-cap", f"hop bound {pq.hop_min}..{pq.hop_max} violates cap {HOP_CAP}")
    if not (1 <= pq.limit <= LIMIT_CAP):
        raise SentinelDenied("policy-limit-cap", f"limit {pq.limit} violates cap {LIMIT_CAP}")


@dataclass
class QueryResult:
    rows: list[dict]
    plan: list[str]
    row_count: int


def _bind(value: str, is_param: bool, params: dict) -> str:
    if not is_param:
        return value
    if value not in params:
        raise CypherRejected("param-missing", f"parameter ${value} not supplied")
    return str(params[value])


def query_cypher(query: str, params: dict | None, adapter: GraphAdapter) -> QueryResult:
    """Graph.QueryCypher(query, params) -> rows + plan. Raises CypherRejected / SentinelDenied."""
    params = params or {}
    pq = parse(query)                 # gateway enforcement
    sentinel_check(pq)                # independent policy enforcement

    anchor = _bind(pq.anchor_value, pq.anchor_is_param, params)
    rel_filter = (_bind(pq.relation_filter, pq.relation_is_param, params)
                  if pq.relation_filter is not None else None)

    hits: list[Hit] = adapter.expand(
        form=anchor, rel_type=pq.rel_type, hop_min=pq.hop_min, hop_max=pq.hop_max,
        relation_filter=rel_filter, limit=pq.limit,
    )
    # RETURN <tail_var>.<prop>: the fixture models a concept's only property as `form`; other props
    # would be resolved by a node lookup in the real HellGraph binding.
    rows = [{f"{pq.return_var}.{pq.return_prop}": h.tail_form,
             "_path": list(h.path),
             "_truth": {"strength": h.truth.strength, "confidence": h.truth.confidence}}
            for h in hits]
    return QueryResult(rows=rows, plan=pq.plan, row_count=len(rows))
