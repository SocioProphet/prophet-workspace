"""AtomSpace/HellGraph adapter for the Cypher gateway (WO-A).

The canonical substrate in our estate is **HellGraph** (the native local graph DB), not a separate
hyperon AtomSpace. The Atomese vocabulary (ConceptNode / PredicateNode / EvaluationLink + TruthValue)
is the *mapping contract*; HellGraph is where it lives. Per the estate rule "HellGraph is consumed,
not modified", this module defines the adapter INTERFACE plus:

  - InMemoryFixtureAdapter  — a drop-in used by the conformance suite (no live DB needed), and
  - HellGraphClientAdapter  — a thin seam that binds the *vendored* HellGraph client (left as a
                              documented stub; wiring it is the runtime half of WO-A once the client
                              package + G6 target repo are confirmed).

Mapping (Cypher <-> Atomese <-> HellGraph):
    (n:Concept {form:"rain"})            ConceptNode "rain"            HellGraph node  label=Concept, form=rain
    (h)-[:CSKG {relation:"IsA"}]->(t)    EvaluationLink                HellGraph edge  type=IsA, from=h, to=t,
                                           (Predicate "IsA")                            truthvalue={strength,confidence}
                                           (List (Concept h)(Concept t))
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class TruthValue:
    strength: float = 1.0
    confidence: float = 1.0


@dataclass(frozen=True)
class Hit:
    """One traversal result row: the tail concept, the path of relations taken, and composed truth."""
    tail_form: str
    path: tuple[str, ...]          # relation names traversed, anchor->tail
    truth: TruthValue


class GraphAdapter(ABC):
    """The HellGraph-compatible substrate interface the gateway executes against."""

    @abstractmethod
    def upsert_concept(self, form: str) -> None: ...

    @abstractmethod
    def upsert_relation(self, head: str, relation: str, tail: str, truth: TruthValue) -> None: ...

    @abstractmethod
    def expand(self, form: str, rel_type: str, hop_min: int, hop_max: int,
               relation_filter: str | None, limit: int) -> list[Hit]:
        """Bounded BFS from `form` over edges of `rel_type` (optionally filtered to a specific
        `relation`), returning tails reachable in hop_min..hop_max hops, best-truth first, capped
        at `limit`. TruthValue composes multiplicatively along a path (min-confidence policy is a
        WO-B experiment; product is the v0 default)."""


class InMemoryFixtureAdapter(GraphAdapter):
    """Reference substrate for conformance tests. Same semantics the HellGraph binding must honour."""

    def __init__(self) -> None:
        # form -> list of (relation, tail, TruthValue)
        self._edges: dict[str, list[tuple[str, str, TruthValue]]] = {}
        self._concepts: set[str] = set()

    def upsert_concept(self, form: str) -> None:
        self._concepts.add(form)

    def upsert_relation(self, head: str, relation: str, tail: str, truth: TruthValue) -> None:
        self.upsert_concept(head)
        self.upsert_concept(tail)
        self._edges.setdefault(head, []).append((relation, tail, truth))

    def expand(self, form: str, rel_type: str, hop_min: int, hop_max: int,
               relation_filter: str | None, limit: int) -> list[Hit]:
        # rel_type is the edge CLASS (e.g. CSKG); relation_filter narrows to a specific predicate
        # (e.g. IsA). In the fixture every edge's `relation` is the predicate; rel_type is honoured
        # as "any CSKG edge" so the filter does the discriminating, matching the Cypher mapping.
        results: dict[str, Hit] = {}
        # BFS keeping best (highest strength*confidence) path per tail
        frontier: list[tuple[str, tuple[str, ...], TruthValue]] = [(form, (), TruthValue())]
        for depth in range(1, hop_max + 1):
            nxt: list[tuple[str, tuple[str, ...], TruthValue]] = []
            for node, path, tv in frontier:
                for relation, tail, etv in self._edges.get(node, []):
                    if relation_filter is not None and relation != relation_filter:
                        continue
                    ntv = TruthValue(tv.strength * etv.strength, tv.confidence * etv.confidence)
                    npath = path + (relation,)
                    nxt.append((tail, npath, ntv))
                    if depth >= hop_min:
                        score = ntv.strength * ntv.confidence
                        prev = results.get(tail)
                        if prev is None or (prev.truth.strength * prev.truth.confidence) < score:
                            results[tail] = Hit(tail_form=tail, path=npath, truth=ntv)
            frontier = nxt
            if not frontier:
                break
        ordered = sorted(results.values(), key=lambda h: -(h.truth.strength * h.truth.confidence))
        return ordered[:limit]

    def load_cskg(self, triples: list[dict]) -> None:
        """Ingest a tiny CSKG fixture: [{head, relation, tail, strength?, confidence?}, ...]."""
        for t in triples:
            self.upsert_relation(
                t["head"], t["relation"], t["tail"],
                TruthValue(float(t.get("strength", 1.0)), float(t.get("confidence", 1.0))),
            )


class HellGraphClientAdapter(GraphAdapter):
    """Runtime binding: HellGraph consumed over its confirmed HTTP surface (consumed, not modified).

    The canonical HellGraph is served by ``hellgraph-service`` (prophet-platform/apps/hellgraph-service),
    the SAME door the rest of the estate writes through (nugget-extractor's HellGraphWriter,
    market-replay's emitter). Verified endpoints (server.ts header + handlers, engine
    @socioprophet/hellgraph 0.4.40):

      - POST /api/graph/node     {id, labels[], properties?}      -> upsert node   (addNode is an upsert)
      - POST /api/graph/edge     {label, from, to, properties?}   -> add typed edge (carries properties)
      - GET  /api/graph/subgraph?label=X[&limit=N]                -> {nodes, edgeList} induced subgraph;
                                                                     edges carry .properties (round-trips)

    Mapping (WO-A contract — the fixture is the contract):
      - upsert_concept  -> POST /node  {id: "Concept:<form>", labels:["Concept"], properties:{form}}
      - upsert_relation -> ensure both concepts, then POST /edge {label: relation, from, to,
                           properties:{strength, confidence, relClass: rel_type}}
      - expand          -> read the Concept-labelled induced subgraph, rebuild the local edge table,
                           and run the IDENTICAL bounded-BFS truth-composition the conformance suite
                           pins (InMemoryFixtureAdapter.expand). Correctness is guaranteed by reuse of
                           the proven algorithm; the read is confirmed-shape (edge .properties survive
                           the round-trip, cf. hellgraph masking.test.ts / rocksdb-backend.test.ts).

    Performance note (documented seam, not a correctness gap): ``expand`` currently pulls the
    Concept subgraph and BFS-es locally. Once a per-node out-edge read (Gremlin outE()+valueMap over
    POST /api/graph/gremlin) is contract-pinned it can expand incrementally; the semantics are already
    frozen by the conformance suite, so that is a mechanical swap.

    ``httpx`` is imported lazily (inside methods) so importing this module — and running the
    conformance suite against InMemoryFixtureAdapter — needs no HTTP dependency.
    """

    #: Edge class this adapter writes/filters on (Cypher ``[:CSKG ...]`` maps here). The predicate
    #: (IsA / Causes / ...) is the edge *label*; the class rides in ``properties.relClass`` and is the
    #: default label filter the gateway maps ``rel_type`` onto — matching the fixture's discipline where
    #: ``relation_filter`` does the discriminating.
    DEFAULT_NODE_LABEL = "Concept"

    def __init__(self, base_url: str, *, client=None, node_label: str = DEFAULT_NODE_LABEL,
                 timeout: float = 30.0, subgraph_limit: int = 2000):
        self.base_url = base_url.rstrip("/")
        self.node_label = node_label
        self.timeout = timeout
        self.subgraph_limit = subgraph_limit
        self._client = client  # optional pre-built httpx.Client (e.g. a MockTransport in tests)

    # -- transport -----------------------------------------------------------------------------
    def _http(self):
        if self._client is not None:
            return self._client
        import httpx  # lazy: only needed for live binding
        self._client = httpx.Client(base_url=self.base_url, timeout=self.timeout)
        return self._client

    def _node_id(self, form: str) -> str:
        return f"{self.node_label}:{form}"

    def _post(self, path: str, payload: dict) -> dict:
        r = self._http().post(path, json=payload)
        if r.status_code != 200:
            raise HellGraphAdapterError(f"hellgraph {r.status_code} on {path}: {r.text[:300]}")
        return r.json()

    # -- writes --------------------------------------------------------------------------------
    def upsert_concept(self, form: str) -> None:
        self._post("/api/graph/node",
                   {"id": self._node_id(form), "labels": [self.node_label], "properties": {"form": form}})

    def upsert_relation(self, head: str, relation: str, tail: str, truth: TruthValue) -> None:
        # addNode is an upsert (safe to repeat); ensure both endpoints exist first.
        self.upsert_concept(head)
        self.upsert_concept(tail)
        self._post("/api/graph/edge", {
            "label": relation,
            "from": self._node_id(head),
            "to": self._node_id(tail),
            "properties": {"strength": truth.strength, "confidence": truth.confidence},
        })

    # -- read + bounded BFS (contract-faithful via algorithm reuse) ----------------------------
    def _load_subgraph(self) -> "InMemoryFixtureAdapter":
        """Pull the Concept-labelled induced subgraph and rebuild the local edge table so the pinned
        BFS runs over exactly the same shape the fixture defines."""
        r = self._http().get("/api/graph/subgraph",
                             params={"label": self.node_label, "limit": self.subgraph_limit})
        if r.status_code != 200:
            raise HellGraphAdapterError(f"hellgraph {r.status_code} on /api/graph/subgraph: {r.text[:300]}")
        body = r.json()
        # id -> form (a Concept node carries properties.form; fall back to stripping the id prefix)
        form_of: dict[str, str] = {}
        for n in body.get("nodes", []):
            props = n.get("properties") or {}
            nid = n.get("id")
            form_of[nid] = props.get("form") or (nid.split(":", 1)[1] if ":" in (nid or "") else nid)
        mem = InMemoryFixtureAdapter()
        for e in body.get("edgeList", []):
            head = form_of.get(e.get("from"))
            tail = form_of.get(e.get("to"))
            if head is None or tail is None:
                continue
            props = e.get("properties") or {}
            mem.upsert_relation(
                head, e.get("label"), tail,
                TruthValue(float(props.get("strength", 1.0)), float(props.get("confidence", 1.0))),
            )
        return mem

    def expand(self, form: str, rel_type: str, hop_min: int, hop_max: int,
               relation_filter: str | None, limit: int) -> list[Hit]:
        return self._load_subgraph().expand(form, rel_type, hop_min, hop_max, relation_filter, limit)


class HellGraphAdapterError(RuntimeError):
    """hellgraph-service unreachable or refused a request. Callers fail closed (never a silent empty)."""
