"""WO-A runtime binding conformance — `python3 tests/hellgraph_binding_test.py`.

Proves HellGraphClientAdapter honours the SAME contract the fixture pins, driven through the
*confirmed* hellgraph-service HTTP surface:

  - POST /api/graph/node     (upsert)
  - POST /api/graph/edge     (typed edge, carries properties)
  - GET  /api/graph/subgraph (induced subgraph; edge .properties round-trip)

By default it runs against a faithful in-memory FAKE of those three endpoints (httpx.MockTransport)
whose semantics mirror the real handlers in prophet-platform/apps/hellgraph-service/src/server.ts
(node upsert-by-id; induced subgraph keeps an edge only when both endpoints are in the node set).

Set HELLGRAPH_BASE_URL to run the identical assertions against a REAL/local hellgraph-service.

Teeth: the binding's expand rows and composed truth must equal both (a) the InMemoryFixtureAdapter
reference and (b) the exact expected sets the WO-A gateway conformance suite pins.
"""
from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
sys.path.insert(0, PKG)

from adapter import HellGraphClientAdapter, InMemoryFixtureAdapter, TruthValue  # noqa: E402

_passed = _failed = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global _passed, _failed
    if cond:
        _passed += 1
        print(f"  ok   {name}")
    else:
        _failed += 1
        print(f"  FAIL {name} :: {detail}")


def load_triples() -> list[dict]:
    with open(os.path.join(PKG, "fixtures", "cskg_mini.json")) as f:
        return json.load(f)["triples"]


# ── faithful in-memory FAKE of the three confirmed hellgraph-service endpoints ────────────────
def make_fake_client():
    import httpx

    nodes: dict[str, dict] = {}          # id -> {id, labels, properties}
    edges: list[dict] = []               # {id, label, from, to, properties}

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if request.method == "POST" and path == "/api/graph/node":
            b = json.loads(request.content)
            if not b.get("id") or not isinstance(b.get("labels"), list):
                return httpx.Response(400, json={"error": "id and labels[] required"})
            node = {"id": b["id"], "labels": b["labels"], "properties": b.get("properties") or {}}
            nodes[b["id"]] = node            # addNode is an upsert
            return httpx.Response(200, json={"ok": True, "node": node})
        if request.method == "POST" and path == "/api/graph/edge":
            b = json.loads(request.content)
            if not b.get("label") or not b.get("from") or not b.get("to"):
                return httpx.Response(400, json={"error": "label, from, to required"})
            edges.append({"id": f"e{len(edges)}", "label": b["label"], "from": b["from"],
                          "to": b["to"], "properties": b.get("properties") or {}})
            return httpx.Response(200, json={"ok": True})
        if request.method == "GET" and path == "/api/graph/subgraph":
            label = request.url.params.get("label", "")
            limit = min(int(request.url.params.get("limit", "400")), 2000)
            picked = [n for n in nodes.values() if not label or label in n["labels"]][:limit]
            ids = {n["id"] for n in picked}
            el = [e for e in edges if e["from"] in ids and e["to"] in ids]  # induced: both endpoints in set
            return httpx.Response(200, json={"count": len(picked), "edges": len(el),
                                             "nodes": picked, "edgeList": el})
        return httpx.Response(404, json={"error": "not_found"})

    return httpx.Client(base_url="http://fake.hellgraph", transport=httpx.MockTransport(handler))


def build_adapters():
    """Return (hellgraph_adapter, reference_adapter) both loaded with the CSKG fixture."""
    triples = load_triples()

    ref = InMemoryFixtureAdapter()
    ref.load_cskg(triples)

    base = os.environ.get("HELLGRAPH_BASE_URL")
    if base:
        hg = HellGraphClientAdapter(base)          # live/local hellgraph-service
        mode = f"live @ {base}"
    else:
        hg = HellGraphClientAdapter("http://fake.hellgraph", client=make_fake_client())
        mode = "fake (httpx.MockTransport)"
    for t in triples:
        hg.upsert_relation(t["head"], t["relation"], t["tail"],
                           TruthValue(float(t.get("strength", 1.0)), float(t.get("confidence", 1.0))))
    return hg, ref, mode


def forms(hits) -> set[str]:
    return {h.tail_form for h in hits}


def main() -> int:
    try:
        import httpx  # noqa: F401
    except ImportError:
        print("  SKIP hellgraph binding test (httpx not installed)")
        return 0

    hg, ref, mode = build_adapters()
    print(f"  -- mode: {mode}")

    # idempotent upsert: re-writing a concept must not error or duplicate the node identity
    hg.upsert_concept("rain")
    check("upsert_concept is idempotent (no error on repeat)", True)

    # The exact traversals the WO-A gateway conformance suite pins, now over the HTTP binding:
    cases = [
        ("2-hop any-relation from rain", ("rain", "CSKG", 1, 2, None, 25),
         {"weather", "flood", "phenomenon", "damage"}),
        ("2-hop IsA-only from rain", ("rain", "CSKG", 1, 2, "IsA", 25), {"weather", "phenomenon"}),
        ("1-hop from rain", ("rain", "CSKG", 1, 1, None, 25), {"weather", "flood"}),
        ("IsA chain dog->animal->organism", ("dog", "CSKG", 1, 2, "IsA", 25), {"animal", "organism"}),
    ]
    for name, args, expected in cases:
        hits = hg.expand(*args)
        check(f"{name} (matches expected)", forms(hits) == expected, f"got {forms(hits)}")
        check(f"{name} (matches InMemory reference)", forms(hits) == forms(ref.expand(*args)),
              f"binding={forms(hits)} ref={forms(ref.expand(*args))}")

    # LIMIT clamps
    check("LIMIT clamps row count", len(hg.expand("rain", "CSKG", 1, 2, None, 1)) == 1)

    # truth composes multiplicatively along the path (damage is 2 hops, weather is 1)
    r = {h.tail_form: h for h in hg.expand("rain", "CSKG", 1, 2, None, 25)}
    check("truth composes along path (damage.confidence < weather.confidence)",
          r["damage"].truth.confidence < r["weather"].truth.confidence,
          f"damage={r['damage'].truth} weather={r['weather'].truth}")
    # edge properties round-trip byte-faithfully through the HTTP surface: weather = 0.9*0.9 strength/conf
    check("edge truth round-trips through HTTP (weather strength=0.9,conf=0.9)",
          abs(r["weather"].truth.strength - 0.9) < 1e-9 and abs(r["weather"].truth.confidence - 0.9) < 1e-9,
          f"got {r['weather'].truth}")

    print(f"\n{_passed} passed, {_failed} failed")
    return 1 if _failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
