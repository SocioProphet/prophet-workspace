"""Labor-request contract — the request-centric labor loop as spec-as-code (prophet-workspace#108).

The SocioProphet Labor Network charter (v0.1) reframes labor as

    labor = request + response + evidence + fulfillment + trust      (request-centric)

and explicitly REJECTS

    labor = identity + feed + ambient messaging + attention          (feed / vanity)

This module encodes that thesis as a five-stage, receipted chain and gives it TEETH. It does NOT
reinvent the estate's receipt or reputation machinery — it *consumes* them:

  * every stage is receipted on the estate receipt spine (WO-B `proof-artifact-spine`, ADR-0001):
    a labor event that cannot emit a ProofArtifact is not an event (AC-1, the receipt law);
  * evidence grades are the metadata-standards `evidence_grade` E1..E5 ladder (E3+ ⇒ null hypotheses);
  * TRUST binds to a guild-scoped GKN Standing Vector (guild-knowledge-network), NOT a raw popularity
    scalar. A follower / like / global-score number is rejected by construction (charter LN-009,
    "score fit between a request and a response; do not publish a universal human-worth score").

The canonical loop (charter §6): Ask -> Route -> Respond -> Evaluate -> Award -> Deliver -> Update trust.

Run the teeth: `python3 tests/labor_contract_test.py` -> teeth both ways.
"""
from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

# --- consume the receipt spine (WO-B), do not reinvent it -------------------------------------------
_SPINE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "proof-artifact-spine")
sys.path.insert(0, os.path.abspath(_SPINE))
from proof_artifact import RunPackage, emit_proof_artifact, verify_ledger  # noqa: E402

# --- charter vocabulary (LN-002 request taxonomy) --------------------------------------------------
REQUEST_TYPES = {
    "RFI", "RFP", "RFQ", "role", "collaboration", "apprenticeship", "review", "availability",
}
# LN-004: compensation transparency is mandatory EXCEPT for these explicitly-typed exemptions.
COMP_EXEMPT_TYPES = {"volunteer", "mutual_aid", "exploratory"}
# LN-017: the trust ledger records these event types with provenance.
TRUST_EVENTS = {"award", "completion", "reference", "dispute", "appeal", "correction"}
COMPLETION_STATES = {"awarded", "in_progress", "delivered", "disputed", "closed"}

# metadata-standards evidence-grade ladder (E1..E5). E3+ demands falsification (null hypotheses).
EVIDENCE_GRADES = ["E1", "E2", "E3", "E4", "E5"]
NULL_HYPOTHESIS_FLOOR = "E3"

# Fields that would smuggle a feed/vanity reputation in. Their PRESENCE rejects a trust binding.
POPULARITY_SCALAR_FIELDS = {
    "popularity", "followers", "follower_count", "likes", "score", "global_score",
    "employability_score", "endorsement_count", "clout", "reputation_points", "rank",
}
# A guild-scoped GKN standing reference (guild-knowledge-network standing-vector). Guild-scoped by
# construction: "a Master in guild:forensics is a Reader elsewhere until they earn standing there."
_GKN_STANDING_REF = re.compile(r"^gkn:standing:guild:[a-z0-9-]+:(user|agent):[A-Za-z0-9._-]+$")

_ID = {
    "request": re.compile(r"^labor-request:[a-z0-9][a-z0-9:._/@-]{1,160}$"),
    "response": re.compile(r"^labor-response:[a-z0-9][a-z0-9:._/@-]{1,160}$"),
    "evidence": re.compile(r"^labor-evidence:[a-z0-9][a-z0-9:._/@-]{1,160}$"),
    "fulfillment": re.compile(r"^labor-fulfillment:[a-z0-9][a-z0-9:._/@-]{1,160}$"),
    "trust": re.compile(r"^labor-trust:[a-z0-9][a-z0-9:._/@-]{1,160}$"),
}


class LaborContractError(Exception):
    """Raised by verify_labor_chain when a chain violates a contract tooth (code + message)."""

    def __init__(self, code: str, message: str):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


# --- the five typed market objects (charter §3) ----------------------------------------------------
@dataclass
class LaborRequest:
    """The atomic object: a structured request, not a generic post (charter §2, LN-001/003/004)."""
    request_id: str
    requester: str
    request_type: str
    objective: str
    compensation_disclosed: bool
    schedule: str
    deadline: str
    evaluation_criteria: list[dict]
    comp_exempt: bool = False          # true only for volunteer / mutual_aid / exploratory (LN-004)
    receipt_ref: dict | None = None    # {ledger_seq, entry_hash} — stamped by run_labor_loop


@dataclass
class LaborResponse:
    """A structured proposal answering a request (charter §3; LN-016 team bids first-class)."""
    response_id: str
    request_ref: str
    responder: str
    approach: str
    terms: str
    proposed_pricing: str
    is_team_bid: bool = False
    receipt_ref: dict | None = None


@dataclass
class Evidence:
    """An evidence packet, graded on the metadata-standards E1..E5 ladder (charter §7)."""
    evidence_id: str
    response_ref: str
    artifact_refs: list[str]
    evidence_grade: str
    null_hypothesis_ids: list[str] = field(default_factory=list)   # required at E3+ (metadata-standards)
    receipt_ref: dict | None = None


@dataclass
class Fulfillment:
    """The work ledger: milestones, proofs, completion — evidenced fulfillment (charter §3, LN-005/017)."""
    fulfillment_id: str
    award_ref: str                     # the awarded response
    evidence_refs: list[str]           # MUST be non-empty (no evidence => not a fulfillment)
    milestones: list[dict]
    completion_status: str
    receipt_ref: dict | None = None


@dataclass
class TrustBinding:
    """A reputation update. Trust = fulfillment history bound to guild-scoped GKN standing, NOT a
    popularity scalar (charter core operating statement; LN-009 no universal score)."""
    trust_id: str
    subject: str
    fulfillment_ref: str
    event_type: str
    standing_ref: str                  # gkn:standing:guild:<g>:<user|agent>:<id> — guild-scoped
    extra: dict = field(default_factory=dict)   # any raw popularity scalar here is REJECTED
    receipt_ref: dict | None = None


@dataclass
class LaborChain:
    """One request-centric loop: request -> response -> evidence -> fulfillment -> trust."""
    request: LaborRequest
    response: LaborResponse
    evidence: list[Evidence]
    fulfillment: Fulfillment
    trust: TrustBinding


# --- the teeth -------------------------------------------------------------------------------------
def _resolves_on_spine(receipt_ref: dict | None, ledger: Path, stage: str) -> None:
    """LC-2, the receipt law (AC-1). A stage with no receipt, or a receipt that does not resolve to a
    real ledger entry with a matching hash, is not a real stage."""
    if not receipt_ref or "ledger_seq" not in receipt_ref or "entry_hash" not in receipt_ref:
        raise LaborContractError("receipt-required", f"{stage} carries no spine receipt (AC-1)")
    seq = receipt_ref["ledger_seq"]
    want = receipt_ref["entry_hash"]
    found = None
    with open(ledger, encoding="utf-8") as f:
        import json
        for line in f:
            line = line.strip()
            if not line:
                continue
            e = json.loads(line)
            if e.get("ledgerSeq") == seq:
                found = e
                break
    if found is None:
        raise LaborContractError("receipt-unresolved", f"{stage} receipt seq {seq} not on the spine")
    if found.get("entryHash") != want:
        raise LaborContractError("receipt-mismatch", f"{stage} receipt hash does not match spine seq {seq}")


def verify_labor_chain(chain: LaborChain, ledger: Path) -> dict:
    """Verify a request-centric labor loop. Returns a verification record on success; raises
    LaborContractError on the first violated tooth.

    Teeth (feed / vanity model rejected by construction):
      LC-0  well-formed ids + charter vocabulary (LN-002 taxonomy, LN-017 events).
      LC-1  chain integrity: response->request, evidence->response, fulfillment->response, trust->fulfillment.
      LC-2  receipt law (AC-1): every stage resolves to a verified ProofArtifact on the receipt spine.
      LC-3  evidence law (LN-005/§7): fulfillment cites >=1 evidence; each graded; E3+ => null hypotheses.
      LC-4  trust=standing law (charter core / LN-009): trust binds to guild-scoped GKN standing and
            carries NO raw popularity scalar.
      LC-5  compensation transparency (LN-004): comp disclosed unless typed volunteer/mutual_aid/exploratory.
    """
    ledger = Path(ledger)
    r, resp, fulf, trust = chain.request, chain.response, chain.fulfillment, chain.trust

    # LC-0 well-formedness + vocabulary ------------------------------------------------------------
    if not _ID["request"].match(r.request_id):
        raise LaborContractError("id-malformed", f"bad request_id {r.request_id!r}")
    if r.request_type not in REQUEST_TYPES:
        raise LaborContractError("type-unknown", f"request_type {r.request_type!r} not in LN-002 taxonomy")
    if not _ID["response"].match(resp.response_id):
        raise LaborContractError("id-malformed", f"bad response_id {resp.response_id!r}")
    if not _ID["fulfillment"].match(fulf.fulfillment_id):
        raise LaborContractError("id-malformed", f"bad fulfillment_id {fulf.fulfillment_id!r}")
    if fulf.completion_status not in COMPLETION_STATES:
        raise LaborContractError("status-unknown", f"completion_status {fulf.completion_status!r} unknown")
    if not _ID["trust"].match(trust.trust_id):
        raise LaborContractError("id-malformed", f"bad trust_id {trust.trust_id!r}")
    if trust.event_type not in TRUST_EVENTS:
        raise LaborContractError("event-unknown", f"trust event_type {trust.event_type!r} not in LN-017")

    # LC-1 chain integrity -------------------------------------------------------------------------
    if resp.request_ref != r.request_id:
        raise LaborContractError("chain-broken", "response.request_ref does not point to the request")
    ev_by_id = {}
    for ev in chain.evidence:
        if not _ID["evidence"].match(ev.evidence_id):
            raise LaborContractError("id-malformed", f"bad evidence_id {ev.evidence_id!r}")
        if ev.response_ref != resp.response_id:
            raise LaborContractError("chain-broken", f"{ev.evidence_id} does not point to the response")
        ev_by_id[ev.evidence_id] = ev
    if fulf.award_ref != resp.response_id:
        raise LaborContractError("chain-broken", "fulfillment.award_ref does not point to the awarded response")
    if trust.fulfillment_ref != fulf.fulfillment_id:
        raise LaborContractError("chain-broken", "trust.fulfillment_ref does not point to the fulfillment")

    # LC-5 compensation transparency (LN-004) ------------------------------------------------------
    if not r.comp_exempt and not r.compensation_disclosed:
        raise LaborContractError(
            "compensation-hidden",
            "labor request must disclose compensation unless explicitly typed volunteer/mutual_aid/"
            "exploratory (LN-004)")

    # LC-3 evidence law (LN-005 / §7) --------------------------------------------------------------
    if not fulf.evidence_refs:
        raise LaborContractError(
            "no-evidence",
            "fulfillment cites no evidence — a fulfillment with no evidence is not a fulfillment (LN-005)")
    for ref in fulf.evidence_refs:
        ev = ev_by_id.get(ref)
        if ev is None:
            raise LaborContractError("evidence-dangling", f"fulfillment cites unknown evidence {ref!r}")
        if not ev.artifact_refs:
            raise LaborContractError("evidence-empty", f"{ev.evidence_id} carries no artifact refs")
        if ev.evidence_grade not in EVIDENCE_GRADES:
            raise LaborContractError("grade-unknown", f"{ev.evidence_id} grade {ev.evidence_grade!r} not E1..E5")
        if EVIDENCE_GRADES.index(ev.evidence_grade) >= EVIDENCE_GRADES.index(NULL_HYPOTHESIS_FLOOR):
            if not ev.null_hypothesis_ids:
                raise LaborContractError(
                    "null-hypotheses-required",
                    f"{ev.evidence_id} is {ev.evidence_grade} (>= E3) and must attach null_hypothesis_ids "
                    "(metadata-standards)")

    # LC-4 trust = guild-scoped standing, NOT a popularity scalar ----------------------------------
    smuggled = POPULARITY_SCALAR_FIELDS & set(trust.extra)
    if smuggled:
        raise LaborContractError(
            "vanity-scalar",
            f"trust binding carries popularity scalar(s) {sorted(smuggled)} — the feed/vanity model is "
            "rejected by construction (charter core; LN-009)")
    if not isinstance(trust.standing_ref, str) or not _GKN_STANDING_REF.match(trust.standing_ref):
        raise LaborContractError(
            "trust-not-standing",
            f"trust.standing_ref {trust.standing_ref!r} is not a guild-scoped GKN standing reference "
            "(gkn:standing:guild:<g>:<user|agent>:<id>). Trust must bind to epistemic standing, not a score.")

    # LC-2 receipt law (AC-1) — verify the spine, then that every stage resolves on it --------------
    ok, msg = verify_ledger(ledger)
    if not ok:
        raise LaborContractError("spine-corrupt", f"receipt spine failed verification: {msg}")
    _resolves_on_spine(r.receipt_ref, ledger, "request")
    _resolves_on_spine(resp.receipt_ref, ledger, "response")
    for ev in chain.evidence:
        _resolves_on_spine(ev.receipt_ref, ledger, ev.evidence_id)
    _resolves_on_spine(fulf.receipt_ref, ledger, "fulfillment")
    _resolves_on_spine(trust.receipt_ref, ledger, "trust")

    return {
        "verified": True,
        "request_type": r.request_type,
        "stages_receipted": 4 + len(chain.evidence),
        "trust_event": trust.event_type,
        "standing_ref": trust.standing_ref,
        "spine": msg,
    }


# --- reference driver: run the loop, receipting every stage on the spine ---------------------------
def _emit(ledger: Path, agent: str, phase: str, payload: dict) -> dict:
    """Emit one stage's ProofArtifact and return a {ledger_seq, entry_hash} receipt_ref."""
    run = RunPackage(plan=[phase], tool_calls=[], outputs=[payload], policy_report={"labor_stage": phase})
    rec = emit_proof_artifact(
        ledger, extent=f"labor/{payload.get('request_id', payload.get('id', 'na'))}", phase=phase,
        epistemic_level="Derived", agent=agent, inputs=str(payload), run=run)
    return {"ledger_seq": rec["ledgerSeq"], "entry_hash": rec["entryHash"]}


def run_labor_loop(chain: LaborChain, ledger: Path) -> LaborChain:
    """Execute the request-centric loop, stamping each stage with a real spine receipt, then verify.

    This is the reference happy path (charter §6): every stage is receipted BEFORE the trust binding
    is written, so trust can only ever reference receipted, evidenced fulfillment."""
    ledger = Path(ledger)
    chain.request.receipt_ref = _emit(ledger, chain.request.requester, "request",
                                      {"request_id": chain.request.request_id, "type": chain.request.request_type})
    chain.response.receipt_ref = _emit(ledger, chain.response.responder, "response",
                                       {"id": chain.response.response_id, "request_id": chain.request.request_id})
    for ev in chain.evidence:
        ev.receipt_ref = _emit(ledger, chain.response.responder, "evidence",
                               {"id": ev.evidence_id, "grade": ev.evidence_grade})
    chain.fulfillment.receipt_ref = _emit(ledger, chain.response.responder, "fulfillment",
                                          {"id": chain.fulfillment.fulfillment_id,
                                           "status": chain.fulfillment.completion_status})
    chain.trust.receipt_ref = _emit(ledger, "system:trust-ledger", "trust",
                                    {"id": chain.trust.trust_id, "standing": chain.trust.standing_ref})
    verify_labor_chain(chain, ledger)
    return chain
