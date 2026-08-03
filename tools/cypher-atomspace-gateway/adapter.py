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
    """Runtime seam: binds the VENDORED HellGraph client (consumed, not modified).

    Deliberately unimplemented until the HellGraph client package + target repo (gap G6) are
    confirmed. It maps 1:1 onto HellGraph primitives already used elsewhere in the estate
    (nodesByLabel / properties / typed edges / bounded traversal), so wiring it is mechanical:
      - upsert_concept  -> put node {label:'Concept', form}
      - upsert_relation -> put typed edge {type: relation, truthvalue}
      - expand          -> HellGraph bounded BFS by edge type, filtered by relation
    """

    def __init__(self, client=None):
        self._client = client

    def _require(self):
        raise NotImplementedError(
            "HellGraphClientAdapter is a documented seam; bind the vendored HellGraph client "
            "(see docs/adr/ADR-0001 WO-A). Conformance runs against InMemoryFixtureAdapter."
        )

    def upsert_concept(self, form: str) -> None: self._require()
    def upsert_relation(self, head, relation, tail, truth) -> None: self._require()
    def expand(self, form, rel_type, hop_min, hop_max, relation_filter, limit): self._require()
