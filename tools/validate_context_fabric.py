#!/usr/bin/env python3
"""Smoke validate Workspace Context Fabric contracts."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "contracts/workspace/context-fabric"
EXAMPLE = BASE / "context-fabric.v0.1.example.json"
SCHEMAS = [
    "context-graph.schema.json",
    "provider-capture.schema.json",
    "provider-projection.schema.json",
    "share-grant.schema.json",
    "recall-candidate.schema.json",
    "workspace-context-runtime-binding.schema.json",
]


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    try:
        for name in SCHEMAS:
            load(BASE / name)
        example = load(EXAMPLE)
        graph = example["contextGraph"]
        workroom_id = graph["workroomId"]
        graph_id = graph["contextGraphId"]
        capture_id = example["providerCapture"]["providerCaptureId"]
        projection_id = example["providerProjection"]["projectionId"]
        share_id = example["shareGrant"]["shareGrantId"]
        recall_id = example["recallCandidate"]["recallCandidateId"]
        for key in ["providerCapture", "providerProjection", "recallCandidate", "runtimeBinding"]:
            assert example[key]["workroomId"] == workroom_id
            assert example[key]["contextGraphId"] == graph_id
        assert example["shareGrant"]["workroomId"] == workroom_id
        assert example["shareGrant"]["projectionId"] == projection_id
        binding = example["runtimeBinding"]
        assert capture_id in binding["provider"]["captureRefs"]
        assert projection_id in binding["provider"]["projectionRefs"]
        assert share_id in binding["provider"]["shareGrantRefs"]
        assert recall_id in binding["recall"]["recallCandidateRefs"]
    except Exception as exc:
        print(f"ERR: {exc}", file=sys.stderr)
        return 2
    print("OK: Workspace Context Fabric smoke validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
