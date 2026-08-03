"""Sherlock Scout v0 — the thin-slice payoff of the Open Agent Continuum (WO-D of ADR-0001).

Composes the three landed pieces into one grounded, governed, receipted answer:
  - WO-C workspace_ceiling  -> what epistemic level may this principal even claim (meet over mounts,
                               external clamped to Derived); what is reachable (the mount table);
  - WO-A Graph.QueryCypher  -> retrieve 1-2 hop justification from the canonical graph (only over
                               mounted sources; safe-subset enforced);
  - WO-B publish(f_!)       -> emit the answer as a hash-chained, replayable ProofArtifact (AC-1).

The answer card honours the Scout answer contract: concise answer, evidence bullets, citations,
freshness, confidence, missing-info (when low), suggested next actions. It NEVER fabricates grounding:
no retrieval hits => ungrounded => hedged answer + missing-info, still receipted.
"""
from __future__ import annotations

import os
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

_TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in ("cypher-atomspace-gateway", "proof-artifact-spine", "workspace-controller"):
    sys.path.insert(0, os.path.join(_TOOLS, _p))

from adapter import GraphAdapter                                   # noqa: E402  (WO-A)
from gateway import query_cypher                                   # noqa: E402  (WO-A)
from epistemic_ceiling import admit_publish, workspace_ceiling, _RANK, LEVELS  # noqa: E402  (WO-C)
from proof_artifact import RunPackage                              # noqa: E402  (WO-B)
from publish import PublishRequest, publish                        # noqa: E402  (WO-B)

# capabilities that make a mounted source READABLE for retrieval
_READABLE = {"read", "reference"}
_STOP = {"what", "who", "the", "a", "an", "did", "caused", "cause", "of", "to", "is", "was",
         "why", "how", "shutdown", "shut", "down", "happened", "after", "facility"}

# Minimal intent -> relation routing (the retrieval-planner idea, ADR-0001 §5 / Archetype §retrieval).
# A causal question narrows the traversal to Causes edges; a definitional one to IsA. None => any edge.
def _relation_intent(question: str) -> str | None:
    q = question.lower()
    if any(w in q for w in ("caus", "why", "led to", "because", "result")):
        return "Causes"
    if any(w in q for w in ("what is", "what kind", "type of", "is a", "define")):
        return "IsA"
    return None


@dataclass
class AnswerCard:
    answer: str
    grounded: bool
    evidence: list = field(default_factory=list)       # human-readable justification bullets
    citations: list = field(default_factory=list)      # {edge path, tail} objects
    freshness: str = "corpus (fixture)"
    confidence: float = 0.0
    missing_info: str | None = None
    next_actions: list = field(default_factory=lambda: ["open case", "find similar", "escalate"])
    epistemic_level: str = "Speculative"


def _reachable(mount_table: dict) -> list[str]:
    return [e["sourceId"] for e in mount_table["spec"]["entries"]
            if _READABLE & set(e["capabilities"])]


def _lemma(question: str) -> str | None:
    toks = [t for t in re.findall(r"[a-zA-Z][a-zA-Z0-9-]*", question.lower()) if t not in _STOP]
    return toks[0] if toks else None


def answer(question: str, *, mount_table: dict, graph_adapter: GraphAdapter, ledger: Path,
           external: bool, source_levels: dict[str, str] | None = None) -> dict:
    """Produce a grounded, ceiling-governed, receipted answer. Returns {card, receipt}."""
    ceiling = workspace_ceiling(mount_table, external=external, source_levels=source_levels)
    reachable = _reachable(mount_table)
    plan = [f"ceiling={ceiling.level} (meet={ceiling.meet}, external={external})",
            f"reachable_sources={len(reachable)}"]
    tool_calls: list[dict] = []

    lemma = _lemma(question)
    rel = _relation_intent(question)
    hits = []
    if reachable and lemma:
        if rel:
            cy = "MATCH (h:Concept {form:$lemma})-[:CSKG*1..2 {relation:$rel}]->(t) RETURN t.form LIMIT 25"
            params = {"lemma": lemma, "rel": rel}
        else:
            cy = "MATCH (h:Concept {form:$lemma})-[:CSKG*1..2]->(t) RETURN t.form LIMIT 25"
            params = {"lemma": lemma}
        tool_calls.append({"tool": "Graph.QueryCypher", "query": cy, "params": params})
        res = query_cypher(cy, params, graph_adapter)
        hits = res.rows
        plan += [f"intent_relation={rel or 'any'}"] + res.plan

    if hits:
        top = hits[0]
        tail = top["t.form"]
        conf = round(top["_truth"]["strength"] * top["_truth"]["confidence"], 3)
        card = AnswerCard(
            answer=f"{lemma} → {tail} (via {' → '.join(top['_path'])})",
            grounded=True,
            evidence=[f"{lemma} {'/'.join(h['_path'])} {h['t.form']}" for h in hits[:5]],
            citations=[{"tail": h["t.form"], "path": h["_path"]} for h in hits[:5]],
            confidence=conf,
            # grounded => agent-Derived, but never above the workspace ceiling
            epistemic_level=LEVELS[min(_RANK["Derived"], _RANK[ceiling.level])],
        )
    else:
        why = ("no knowledge source is mounted (nothing reachable)" if not reachable
               else "no supporting evidence found in the mounted corpus")
        card = AnswerCard(
            answer="I don't have grounded evidence to answer that.",
            grounded=False, confidence=0.0,
            missing_info=why,
            epistemic_level="Speculative",
            next_actions=["broaden mount (request grant)", "escalate", "ingest source"],
        )

    # AC-2: never publish above the ceiling (defensive; card level is already clamped)
    admit_publish(ceiling, card.epistemic_level)

    receipt = publish(
        PublishRequest(
            agent="sherlock-scout", external=external,
            extent=mount_table["spec"]["declaredExtent"], phase="answer",
            epistemic_level=card.epistemic_level, inputs=question,
            run=RunPackage(plan=plan, tool_calls=tool_calls, outputs=[asdict(card)],
                           policy_report={"offline_first": True, "grounded": card.grounded,
                                          "ceiling": ceiling.level}),
            cover=reachable, existing_covers=[]),
        ledger)
    return {"card": card, "receipt": receipt}
