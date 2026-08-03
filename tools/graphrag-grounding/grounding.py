"""GraphRAG grounded-answer-with-page-reference contract (Knowledge Hub, pw#76).

The GraphRAG page-reference grounding loop (reference frame 5):

    Query → Indexing (Page Contents → vision → KG Indexings + Vector Embeddings)
          → Retrieval (pages) → Generation → **Answer WITH Page Reference**

This module is the *contract* for the last arrow: an answer is only admissible if it carries
page/source references that RESOLVE against the indexed KG+vector store, and only VERIFIES if the
cited pages clear the retrieval-accuracy floor and the answer clears the QA-similarity floor.

Consume-not-fork. This composes three landed pieces already in this repo:
  - the sherlock-scout **AnswerCard** shape (tools/sherlock-scout/scout.py): answer · grounded ·
    citations · confidence · freshness · missing_info · next_actions · epistemic_level. The scout's
    `citations` are graph-edge refs {tail, path}; a GraphRAG answer EXTENDS each citation with a
    resolvable `page_ref` — that page anchor is the gap this contract fills (confirmed absent from
    both sherlock-scout and prophet-platform's graphrag.ts / KnowledgeNugget.sourceRef).
  - the **receipt spine** (tools/proof-artifact-spine): every answer — VERIFY or REJECTED — is
    published as a hash-chained, replayable ProofArtifact (AC-1: no receipt ⇒ no publish). SHA-256
    here is the FIPS 180-4 *algorithm* (not a FIPS-140 module).
  - the **evidence-grade** vocabulary (metadata-standards / tools/metadata-intake): E1..E5,
    Speculative → Corroborated.

Teeth both ways (see grade_answer):
  - page-refs present, all resolvable, retrieval_page_accuracy ≥ floor, qa_similarity_f1 ≥ qa_floor
      ⇒ **VERIFY**;
  - no page-refs / any unresolvable ref / below the accuracy floor / below the QA floor
      ⇒ **REJECTED**.

Stdlib-only. Import `answer_with_page_reference` for the receipted end-to-end path, or `grade_answer`
for the pure verdict.
"""
from __future__ import annotations

import os
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

from metrics import qa_similarity_f1, retrieval_page_accuracy

# Consume the receipt spine (WO-B). Same sys.path idiom sherlock-scout uses.
_TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_TOOLS, "proof-artifact-spine"))
from proof_artifact import RunPackage, emit_proof_artifact, sha256, verify_ledger  # noqa: E402

# Evidence-grade vocabulary (metadata-standards): E1 Speculative → E5 Corroborated.
EVIDENCE_GRADES = ("E1", "E2", "E3", "E4", "E5")

DEFAULT_ACCURACY_FLOOR = 0.5   # retrieval_page_accuracy floor for VERIFY
DEFAULT_QA_FLOOR = 0.3         # qa_similarity_f1 floor for VERIFY


class GroundingError(Exception):
    pass


# ─── the indexed KG+vector store (retrieval target) ──────────────────────────
@dataclass
class PageIndex:
    """The indexed corpus a page_ref must resolve against — the 'KG Indexings + Vector Embeddings'
    surface of the GraphRAG loop, reduced to what a page_ref needs to be RESOLVABLE: which
    (source_id, page) pairs actually exist in the index. A ref that names a source or page the index
    never ingested is unresolvable — the answer cannot be grounded on it."""

    # source_id -> {"title": str, "pages": set[int]}
    sources: dict

    @staticmethod
    def from_dict(d: dict) -> "PageIndex":
        srcs = {}
        for sid, meta in (d.get("sources") or {}).items():
            pages = set(int(p) for p in (meta.get("pages") or []))
            srcs[sid] = {"title": meta.get("title", sid), "pages": pages}
        return PageIndex(sources=srcs)

    def resolves(self, ref: dict) -> bool:
        sid, page = ref.get("source_id"), ref.get("page")
        src = self.sources.get(sid)
        if src is None or not isinstance(page, int):
            return False
        return page in src["pages"]


def _page_key(ref: dict) -> tuple:
    return (ref.get("source_id"), ref.get("page"))


# ─── the grounded answer (AnswerCard + page references) ───────────────────────
@dataclass
class GroundedAnswer:
    """sherlock-scout AnswerCard EXTENDED with page-referenced citations.

    Each citation carries `page_ref` = {source_id, page, span?, quote?} — the resolvable anchor into
    the indexed store. `evidence`/`freshness`/`next_actions` keep the scout card's shape so a scout
    consumer renders this unchanged."""

    question: str
    answer: str
    grounded: bool
    citations: list = field(default_factory=list)   # [{"claim": str, "page_ref": {source_id,page,..}}]
    evidence: list = field(default_factory=list)
    confidence: float = 0.0
    freshness: str = "corpus (fixture)"
    missing_info: str | None = None
    next_actions: list = field(default_factory=lambda: ["open case", "find similar", "escalate"])
    epistemic_level: str = "Speculative"

    def page_refs(self) -> list:
        return [c["page_ref"] for c in self.citations if isinstance(c, dict) and c.get("page_ref")]


# ─── the verdict (teeth) ─────────────────────────────────────────────────────
def grade_answer(
    answer: dict | GroundedAnswer,
    index: PageIndex | dict,
    gold: dict,
    *,
    floor: float = DEFAULT_ACCURACY_FLOOR,
    qa_floor: float = DEFAULT_QA_FLOOR,
) -> dict:
    """Grade a grounded answer against the index + gold. Returns a verdict dict:

        {verdict: "VERIFY"|"REJECTED", reasons:[...], metrics:{...}, floor, qa_floor}

    gold = {"answer": <reference answer text>, "pages": [{"source_id","page"}, ...]}.

    An answer VERIFIES iff (and the order is the fail-closed sequence):
      1. it carries at least one page_ref,
      2. every page_ref RESOLVES against the index,
      3. retrieval_page_accuracy(cited_pages, gold_pages) ≥ floor,
      4. qa_similarity_f1(answer_text, gold_answer) ≥ qa_floor.
    Any failure ⇒ REJECTED with the specific reason. No page_refs ⇒ REJECTED (cannot be grounded).
    """
    card = answer if isinstance(answer, GroundedAnswer) else GroundedAnswer(**answer)
    idx = index if isinstance(index, PageIndex) else PageIndex.from_dict(index)

    refs = card.page_refs()
    gold_pages = {(_page_key(p)) for p in gold.get("pages", [])}
    cited_pages = {_page_key(r) for r in refs}

    rpa = retrieval_page_accuracy(cited_pages, gold_pages)
    qaf1 = qa_similarity_f1(card.answer, gold.get("answer", ""))
    unresolved = [r for r in refs if not idx.resolves(r)]

    metrics = {
        "retrieval_page_accuracy": rpa,
        "qa_similarity_f1": qaf1,
        "page_refs_total": len(refs),
        "page_refs_resolved": len(refs) - len(unresolved),
    }

    reasons: list[str] = []
    if not refs:
        reasons.append("no page references: a grounded answer MUST cite resolvable page/source refs")
    elif unresolved:
        pretty = ", ".join(f"{_page_key(r)[0]}#p{_page_key(r)[1]}" for r in unresolved)
        reasons.append(f"unresolvable page references (not in index): {pretty}")
    else:
        if rpa < floor:
            reasons.append(f"retrieval_page_accuracy {rpa:.3f} < floor {floor:.3f}")
        if qaf1 < qa_floor:
            reasons.append(f"qa_similarity_f1 {qaf1:.3f} < floor {qa_floor:.3f}")

    verdict = "VERIFY" if not reasons else "REJECTED"
    return {"verdict": verdict, "reasons": reasons, "metrics": metrics,
            "floor": floor, "qa_floor": qa_floor}


# ─── the receipted end-to-end path ───────────────────────────────────────────
def answer_with_page_reference(
    card: dict | GroundedAnswer,
    index: PageIndex | dict,
    gold: dict,
    *,
    ledger: Path,
    floor: float = DEFAULT_ACCURACY_FLOOR,
    qa_floor: float = DEFAULT_QA_FLOOR,
    agent: str = "graphrag-grounding",
    extent: str = "knowledge-hub/graphrag",
    external: bool = False,
) -> dict:
    """Grade + RECEIPT. Every answer is published as a hash-chained ProofArtifact regardless of
    verdict (AC-1). Returns {answer, verdict, receipt}. Raises GroundingError if the ledger cannot be
    written (no receipt ⇒ no publish)."""
    ga = card if isinstance(card, GroundedAnswer) else GroundedAnswer(**card)
    verdict = grade_answer(ga, index, gold, floor=floor, qa_floor=qa_floor)

    # External principals are capped at Derived (STAR-1); a REJECTED answer never claims above
    # Speculative. A VERIFYing answer is agent-Derived.
    if verdict["verdict"] != "VERIFY":
        level = "Speculative"
    else:
        level = "Derived"
    if external and level != "Speculative":
        level = "Derived"
    ga.epistemic_level = level

    run = RunPackage(
        plan=[f"grade(floor={floor}, qa_floor={qa_floor})", f"verdict={verdict['verdict']}"],
        tool_calls=[{"tool": "grade_answer", "metrics": verdict["metrics"]}],
        outputs=[asdict(ga)],
        policy_report={
            "grounded": ga.grounded,
            "verdict": verdict["verdict"],
            "reasons": verdict["reasons"],
            "metrics": verdict["metrics"],
            "floors": {"retrieval_page_accuracy": floor, "qa_similarity_f1": qa_floor},
            "grounded_answer_contract": "graphrag-grounding/v0.1",
        },
    )
    try:
        receipt = emit_proof_artifact(
            Path(ledger), extent=extent, phase="answer", epistemic_level=level,
            agent=agent, inputs=ga.question, run=run,
            inclusion_record={"page_refs": [_page_key(r) for r in ga.page_refs()]},
        )
    except Exception as e:  # proof_artifact raises ProofArtifactError on ledger write failure
        raise GroundingError(f"answer not published — receipt emit failed: {e}") from e

    return {"answer": asdict(ga), "verdict": verdict, "receipt": receipt}


# re-export for consumers that want to verify the ledger after a batch of answers
__all__ = [
    "PageIndex", "GroundedAnswer", "grade_answer", "answer_with_page_reference",
    "GroundingError", "verify_ledger", "sha256", "EVIDENCE_GRADES",
    "DEFAULT_ACCURACY_FLOOR", "DEFAULT_QA_FLOOR",
]
