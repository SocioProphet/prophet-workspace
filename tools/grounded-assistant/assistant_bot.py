"""Grounded-assistant contract — the "Virtual Assistant for Technical Support" product surface.

prophet-workspace#76 item 8, on the Open Agent Continuum (ADR-0001). This is the product-surface
slice of WO-D (Sherlock Scout: a grounded RAG answer, receipted): a set of domain-scoped support
bots, each of which must answer in the Sherlock-Scout answer-card shape and cannot emit an answer
without evidence, a citation, sufficient confidence, and a **receipt** on the estate spine.

Consume-not-fork:
  - the receipt spine is `../proof-artifact-spine` (WO-B). We import `publish`/`RunPackage` and emit a
    ProofArtifact on the same hash-chained ledger. AC-1 (the receipt law) is inherited verbatim: an
    answer that cannot emit a receipt is not an answer.
  - the answer-card shape is Sherlock's evidence-answer contract
    (sherlock-search/docs/evidence-answer-contract.md): answer + evidence(refs) + citations +
    freshness + confidence + missing-info + next-actions. We do not re-derive it.
  - each bot maps to an agent-registry AgentSpec principal (agent://…); bots enter as EXTERNAL
    principals and are therefore capped at the `Derived` epistemic ceiling (STAR-1 / AC-2) by the spine.

The teeth (both ways) live in `tests/grounded_assistant_test.py`.
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

# Consume the receipt spine (WO-B) — do not fork it.
_SPINE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "proof-artifact-spine")
sys.path.insert(0, os.path.abspath(_SPINE))

from proof_artifact import RunPackage  # noqa: E402
from publish import PublishDenied, PublishRequest, publish  # noqa: E402

# Grounding floor: an answer at or below this confidence is not grounded enough to publish.
# A support bot that cannot clear the floor must abstain (return missing-info), not guess.
CONFIDENCE_FLOOR = 0.60


class AssistantRejected(Exception):
    """A draft answer that fails the grounding gate. `code` is machine-readable for the caller/UI."""

    def __init__(self, code: str, message: str):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


@dataclass(frozen=True)
class AssistantBot:
    """Descriptor for one domain-scoped support bot (spec-as-code; instances in bots.json)."""

    id: str                              # bot://socioprophet/tech-support/<name>
    domain: str                          # the knowledge scope it is grounded by
    skill: str                           # the grounded skill it invokes
    required_client_fields: list[str]    # fields that MUST be gathered before this bot can answer
    agent_spec_ref: str = ""             # agent-registry principal (agent://…) — external, ≤ Derived

    def missing_fields(self, client: dict) -> list[str]:
        """Which required client fields are absent or empty in the gathered client info."""
        return [f for f in self.required_client_fields if not client.get(f)]


@dataclass
class DraftAnswerCard:
    """A proposed answer in the Sherlock-Scout answer-card shape, before the grounding gate.

    Mirrors sherlock-search/docs/evidence-answer-contract.md: an answer carries its supporting
    evidence refs, its citations, freshness, a confidence, what info is still missing, and next
    actions. `receipt` is filled in by the gate on success (never by the drafter)."""

    answer: str
    evidence: list[str] = field(default_factory=list)      # evidence refs (ids/anchors)
    citations: list[str] = field(default_factory=list)     # source refs shown to the client
    freshness: str = "unknown"                             # fresh | stale | unknown
    confidence: float = 0.0
    missing_info: list[str] = field(default_factory=list)
    next_actions: list[str] = field(default_factory=list)
    receipt: dict | None = None

    def to_dict(self) -> dict:
        return {
            "answer": self.answer,
            "evidence": list(self.evidence),
            "citations": list(self.citations),
            "freshness": self.freshness,
            "confidence": self.confidence,
            "missingInfo": list(self.missing_info),
            "nextActions": list(self.next_actions),
            "receipt": self.receipt,
        }


def answer(bot: AssistantBot, client: dict, draft: DraftAnswerCard, ledger: Path) -> DraftAnswerCard:
    """The grounding gate. Returns the card stamped with its receipt, or raises AssistantRejected.

    Teeth, in order:
      1. required client fields for this bot's intent must be gathered   -> else `missing-fields`
      2. the answer must be grounded: >=1 evidence ref AND >=1 citation   -> else `ungrounded`
      3. confidence must clear the floor                                  -> else `low-confidence`
      4. a receipt MUST be emitted on the spine (fail-closed, AC-1)       -> else `receipt-required`
    An answer that survives all four carries an auditable ProofArtifact; nothing else is an answer.
    """
    # 1) client-info completeness for the intent
    missing = bot.missing_fields(client)
    if missing:
        raise AssistantRejected(
            "missing-fields",
            f"{bot.id} requires client fields {missing} before answering")

    # 2) grounding: evidence refs + citations
    if not draft.evidence:
        raise AssistantRejected("ungrounded", "answer carries no evidence refs")
    if not draft.citations:
        raise AssistantRejected("ungrounded", "answer carries no citations")

    # 3) confidence floor
    if draft.confidence < CONFIDENCE_FLOOR:
        raise AssistantRejected(
            "low-confidence",
            f"confidence {draft.confidence:.2f} below floor {CONFIDENCE_FLOOR:.2f}")

    # 4) emit the receipt — fail-closed (AC-1). No receipt ⇒ not an answer.
    run = RunPackage(
        plan=["gather-client-info", "ground:" + bot.skill, "answer-card"],
        tool_calls=[{"tool": bot.skill, "domain": bot.domain, "client": sorted(client.keys())}],
        outputs=[{
            "answer": draft.answer,
            "evidence": list(draft.evidence),
            "citations": list(draft.citations),
            "freshness": draft.freshness,
            "confidence": draft.confidence,
        }],
        policy_report={"grounded": True, "confidence_floor": CONFIDENCE_FLOOR, "bot": bot.id},
    )
    req = PublishRequest(
        agent=bot.agent_spec_ref or bot.id,
        external=True,                     # bots are external principals -> capped at Derived (STAR-1)
        extent=f"tech-support/{bot.domain}",
        phase="assist-session",
        epistemic_level="Derived",
        inputs=draft.answer,
        run=run,
        cover=list(draft.evidence),
    )
    try:
        receipt = publish(req, ledger)
    except (PublishDenied, Exception) as e:  # noqa: BLE001 — any emission failure fails the answer
        if isinstance(e, AssistantRejected):
            raise
        raise AssistantRejected("receipt-required", f"answer refused — no receipt could be emitted ({e})") from e

    draft.receipt = receipt
    return draft


# ---------------------------------------------------------------------------
# The five named bots (transcribed from the reference UI), as spec-as-code instances.
# Kept byte-aligned with bots.json — the test asserts the two agree.
# ---------------------------------------------------------------------------
BOTS: dict[str, AssistantBot] = {
    "qa": AssistantBot(
        id="bot://socioprophet/tech-support/qa",
        domain="product-knowledge",
        skill="grounded-qa",
        required_client_fields=["product_model"],
        agent_spec_ref="agent://socioprophet/tech-support/qa",
    ),
    "qa-flex": AssistantBot(
        id="bot://socioprophet/tech-support/qa-flex",
        domain="product-knowledge",
        skill="grounded-qa-flex",
        required_client_fields=["product_model", "issue_summary"],
        agent_spec_ref="agent://socioprophet/tech-support/qa-flex",
    ),
    "parts-replacement": AssistantBot(
        id="bot://socioprophet/tech-support/parts-replacement",
        domain="parts-catalog",
        skill="parts-lookup",
        required_client_fields=["product_model", "part_id"],
        agent_spec_ref="agent://socioprophet/tech-support/parts-replacement",
    ),
    "service-request-status": AssistantBot(
        id="bot://socioprophet/tech-support/service-request-status",
        domain="service-requests",
        skill="service-request-status",
        required_client_fields=["service_request_id"],
        agent_spec_ref="agent://socioprophet/tech-support/service-request-status",
    ),
    "warranty-check": AssistantBot(
        id="bot://socioprophet/tech-support/warranty-check",
        domain="warranty-registry",
        skill="warranty-lookup",
        required_client_fields=["product_serial"],
        agent_spec_ref="agent://socioprophet/tech-support/warranty-check",
    ),
}
