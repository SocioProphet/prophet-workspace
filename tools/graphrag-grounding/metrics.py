"""Computable, teeth-backed GraphRAG grounding metrics (pw#76, reference frame 5).

Two metrics, both pure and deterministic (stdlib-only):

  - retrieval_page_accuracy(cited_pages, gold_pages): of the (source_id, page) pairs the answer
    CITED, what fraction are correct against the gold page set — page-reference precision. This is the
    teeth on "Retrieval Page Accuracy": citing pages that are not the grounding pages drives it down,
    and it gates VERIFY via the accuracy floor. Empty citation set ⇒ 0.0 (an answer that cites nothing
    has no page-reference accuracy to credit).

  - qa_similarity_f1(pred, gold): SQuAD-style token-level F1 between the predicted answer and the
    reference answer — the "Question-Answer Similarity F1" of the frame. Case/punct/article-normalized
    bag-of-tokens overlap → precision, recall, F1. This is what stops a page-correct answer whose PROSE
    is wrong/empty from VERIFYing.

Both return floats in [0.0, 1.0].
"""
from __future__ import annotations

import re
import string
from collections import Counter
from typing import Iterable

_ARTICLES = {"a", "an", "the"}
_PUNCT = str.maketrans("", "", string.punctuation)


def retrieval_page_accuracy(cited_pages: Iterable, gold_pages: Iterable) -> float:
    """|cited ∩ gold| / |cited| over (source_id, page) pairs. Precision of the cited page set."""
    cited = {tuple(p) if isinstance(p, list) else p for p in cited_pages}
    gold = {tuple(p) if isinstance(p, list) else p for p in gold_pages}
    if not cited:
        return 0.0
    hit = len(cited & gold)
    return round(hit / len(cited), 6)


def _normalize(text: str) -> list[str]:
    """SQuAD normalization: lowercase, strip punctuation, drop articles, collapse whitespace."""
    text = (text or "").lower().translate(_PUNCT)
    toks = re.findall(r"[a-z0-9√²]+", text)
    return [t for t in toks if t not in _ARTICLES]


def qa_similarity_f1(pred: str, gold: str) -> float:
    """SQuAD-style token-level F1 between predicted and reference answers."""
    p, g = _normalize(pred), _normalize(gold)
    if not p and not g:
        return 1.0
    if not p or not g:
        return 0.0
    common = Counter(p) & Counter(g)
    overlap = sum(common.values())
    if overlap == 0:
        return 0.0
    precision = overlap / len(p)
    recall = overlap / len(g)
    return round(2 * precision * recall / (precision + recall), 6)


__all__ = ["retrieval_page_accuracy", "qa_similarity_f1"]
