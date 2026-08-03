"""Tiny in-memory evaluator for the Qdrant filter shape + fixture payloads (consume-not-fork).

No live Qdrant is stood up (live execution is a runtime concern filed to @mdheller). This applies the
SAME `{must:[...], must_not:[...]}` filter shape memoryd's `qdrant_index.py` sends
(`match:{value}`, `match:{any}`, `range:{gte/gt/lte/lt}`, `is_empty:{key}`) to fixture payloads, so a
constructed filter can be EXECUTED against representative points and its hits asserted. The operator
semantics mirror the AgenticaForge `MetadataFilter` reference.
"""
from __future__ import annotations

# memorymesh-recall-shaped points (subset of the qdrant_index.py payload keys) + a created_at date.
POINTS = [
    {"id": "p1", "payload": {"memory_class": "fact", "tags": ["climate"], "user_id": "u1",
                              "source_interface": "cli", "created_at": "2020-03-01"}},
    {"id": "p2", "payload": {"memory_class": "decision", "tags": ["policy"], "user_id": "u1",
                              "source_interface": "web", "created_at": "2021-06-15"}},
    {"id": "p3", "payload": {"memory_class": "fact", "tags": ["climate", "coastal"], "user_id": "u2",
                              "source_interface": "cli", "created_at": "2023-11-20"}},
    {"id": "p4", "payload": {"memory_class": "summary", "tags": ["climate"], "user_id": "u2",
                              "source_interface": "api", "created_at": "2025-02-02"}},
    {"id": "p5", "payload": {"memory_class": "scratch", "tags": [], "user_id": "u3",
                              "source_interface": "cli"}},  # no created_at → is_empty
]


def _match_value(pv, cond_val) -> bool:
    if isinstance(pv, list):
        return cond_val in pv
    return pv == cond_val


def _match_any(pv, anyvals) -> bool:
    if isinstance(pv, list):
        return any(v in pv for v in anyvals)
    return pv in anyvals


def _range_ok(pv, r: dict) -> bool:
    if pv is None:
        return False
    if "gt" in r and not pv > r["gt"]:
        return False
    if "gte" in r and not pv >= r["gte"]:
        return False
    if "lt" in r and not pv < r["lt"]:
        return False
    if "lte" in r and not pv <= r["lte"]:
        return False
    return True


def _cond_holds(payload: dict, cond: dict) -> bool:
    if "is_empty" in cond:
        key = cond["is_empty"]["key"]
        v = payload.get(key)
        return v is None or v == [] or v == ""
    key = cond["key"]
    pv = payload.get(key)
    if "match" in cond:
        m = cond["match"]
        if "value" in m:
            return _match_value(pv, m["value"])
        if "any" in m:
            return _match_any(pv, m["any"])
    if "range" in cond:
        return _range_ok(pv, cond["range"])
    return False


def apply_filter(flt: dict, points=POINTS) -> list[str]:
    """Return the ids of points satisfying the Qdrant filter (must AND, must_not NAND)."""
    hits = []
    for pt in points:
        payload = pt["payload"]
        if all(_cond_holds(payload, c) for c in flt.get("must", [])) and \
           not any(_cond_holds(payload, c) for c in flt.get("must_not", [])):
            hits.append(pt["id"])
    return hits
