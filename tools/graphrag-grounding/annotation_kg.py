"""annotation → KG contract (Knowledge Hub annotation overlay, pw#76).

An annotation (select text → Highlight + Comment + Tags) becomes a **provenance-sealed** KG node/edge
write plan. This is the contract the annotation overlay emits into the knowledge graph.

Consume-not-fork: the write plan is shaped for HellGraph's supported write path — the façade
`addNode(id, labels, props)` (hellgraph ts/src/cypher.ts, store.ts) plus relationship edges. The seal
is SHA-256 (FIPS 180-4 algorithm) over the canonical annotation core, matching the receipt-spine seal
discipline. Evidence grade uses the metadata-standards E1..E5 vocabulary.

NO LIVE WRITE. `annotation_to_kg` is a pure function returning the write plan; committing it to a live
HellGraph store is a separate, gated runtime step (out of scope here — fixtures only).
"""
from __future__ import annotations

import json
import os
import sys

_TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_TOOLS, "proof-artifact-spine"))
from proof_artifact import canonical, sha256  # noqa: E402  (same seal discipline as the receipt spine)

EVIDENCE_GRADES = ("E1", "E2", "E3", "E4", "E5")
_SEALED_FIELDS = ("doc_id", "page", "span", "highlighted_text", "note", "tags", "author", "created_at")


class AnnotationError(Exception):
    pass


def _require(ann: dict, key: str):
    if key not in ann or ann[key] in (None, ""):
        raise AnnotationError(f"annotation missing required field: {key}")
    return ann[key]


def annotation_to_kg(ann: dict, *, evidence_class: str = "Primary", evidence_grade: str = "E2") -> dict:
    """Turn one annotation into a provenance-sealed KG write plan.

    Required annotation fields: doc_id, page, highlighted_text, author, created_at.
    Optional: id, source_id, span {start,end}, note, tags[].

    Returns {"nodes": [...], "edges": [...], "provenance": {...}} where every node matches the
    HellGraph addNode contract: {"id": str, "labels": [str], "props": {..}}.
    """
    if evidence_grade not in EVIDENCE_GRADES:
        raise AnnotationError(f"evidence_grade must be one of {EVIDENCE_GRADES}, got {evidence_grade!r}")

    doc_id = _require(ann, "doc_id")
    page = _require(ann, "page")
    text = _require(ann, "highlighted_text")
    author = _require(ann, "author")
    created_at = _require(ann, "created_at")
    if not isinstance(page, int):
        raise AnnotationError("annotation.page must be an integer page number")

    span = ann.get("span") or {}
    note = ann.get("note", "")
    tags = list(ann.get("tags") or [])
    source_id = ann.get("source_id", doc_id)

    # provenance seal over the canonical annotation core (tamper-evident, deterministic)
    core = {k: ann.get(k) for k in _SEALED_FIELDS}
    core["tags"] = sorted(tags)  # order-independent seal
    seal = sha256(canonical(core))
    ann_id = ann.get("id") or ("ann:" + seal.split(":", 1)[1][:16])

    provenance = {
        "seal": seal,
        "hash_algo": "sha256 (FIPS 180-4)",
        "sealed_fields": list(_SEALED_FIELDS),
        "evidence_class": evidence_class,
        "evidence_grade": evidence_grade,
    }

    nodes = [
        {
            "id": ann_id,
            "labels": ["Annotation"],
            "props": {
                "highlighted_text": text,
                "note": note,
                "page": page,
                "span_start": span.get("start"),
                "span_end": span.get("end"),
                "author": author,
                "created_at": created_at,
                "source_id": source_id,
                "provenance_seal": seal,
                "evidence_class": evidence_class,
                "evidence_grade": evidence_grade,
            },
        },
        # Document node is upsert-shaped (id stable across annotations on the same doc)
        {"id": doc_id, "labels": ["Document"], "props": {"source_id": source_id}},
    ]
    edges = [
        {
            "from": ann_id, "rel": "ANNOTATES", "to": doc_id,
            "props": {"page": page, "span_start": span.get("start"), "span_end": span.get("end")},
        }
    ]
    for t in tags:
        tag_id = "tag:" + str(t)
        nodes.append({"id": tag_id, "labels": ["Tag"], "props": {"name": t}})
        edges.append({"from": ann_id, "rel": "TAGGED", "to": tag_id, "props": {}})

    return {"nodes": nodes, "edges": edges, "provenance": provenance}


def is_valid_write_node(node: dict) -> bool:
    """A node conforms to the HellGraph addNode(id, labels, props) write contract."""
    return (
        isinstance(node, dict)
        and isinstance(node.get("id"), str) and node["id"]
        and isinstance(node.get("labels"), list) and all(isinstance(x, str) for x in node["labels"])
        and node["labels"]
        and isinstance(node.get("props"), dict)
    )


if __name__ == "__main__":
    # tiny CLI: annotation_kg.py <annotation.json>  → prints the write plan
    import sys as _s
    src = json.loads(open(_s.argv[1], encoding="utf-8").read())
    print(json.dumps(annotation_to_kg(src), indent=2, ensure_ascii=False))
