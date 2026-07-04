#!/usr/bin/env python3
"""Smoke validate the PersonalContextGraph (ego-scoped CSKG) contract.

Checks the schema loads, the example conforms to the key invariants (single Self
anchor, person scope, provenance-bound sources, reference-only external links via
ProviderProjection), and that cross-refs between the graph and its external
projection are consistent — mirroring validate_context_fabric.py.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "contracts/workspace/context-fabric"
SCHEMA = BASE / "personal-context-graph.schema.json"
PROJECTION_SCHEMA = BASE / "provider-projection.schema.json"
EXAMPLE = BASE / "personal-context-graph.v0.1.example.json"


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    try:
        schema = load(SCHEMA)
        load(PROJECTION_SCHEMA)
        example = load(EXAMPLE)
        graph = example["personalContextGraph"]

        # Required fields present.
        for key in schema["required"]:
            assert key in graph, f"missing required field {key!r}"

        # Person-scoped, anchored on a single Self that is itself a node.
        assert graph["subjectScope"] == "person"
        assert graph["selfRef"] in graph["nodeRefs"], "selfRef must be a node in the graph"

        # Every source is a WorkspaceSource (Layer-1 canonical object) → provenance-bound.
        assert all(s.startswith("workspace-source:") for s in graph["sourceRefs"]), \
            "sourceRefs must be workspace-source ids"

        # Vocabulary conformance.
        node_types = set(schema["properties"]["nodeTypeVocabulary"]["items"]["enum"])
        relations = set(schema["properties"]["relationVocabulary"]["items"]["enum"])
        assert set(graph["nodeTypeVocabulary"]) <= node_types, "unknown node type in vocabulary"
        assert set(graph["relationVocabulary"]) <= relations, "unknown relation in vocabulary"

        # External links cross the membrane ONLY as a ProviderProjection, and the
        # graph's externalProjectionRefs match the projection id.
        projection = example["externalProjection"]
        assert projection["projectionId"] in graph["externalProjectionRefs"]
        assert projection["contextGraphId"] == graph["personalContextGraphId"]
        # The membrane withholds at least the private relationship (nothing private egresses).
        assert projection["membraneDecisionRef"], "external projection needs a membrane decision"
        withheld = {w["ref"] for w in projection["withheldRefs"]}
        included = set(projection["includedNodeRefs"])
        assert included.isdisjoint(withheld), "a node cannot be both included and withheld"
    except Exception as exc:  # noqa: BLE001
        print(f"ERR: {exc}", file=sys.stderr)
        return 2
    print("OK: PersonalContextGraph smoke validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
