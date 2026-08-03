"""Labor-request contract conformance — `python3 tests/labor_contract_test.py` (no pytest dep).

Teeth BOTH ways:
  * a request -> response -> evidence -> fulfillment -> trust loop where every stage is receipted on
    the spine, fulfillment cites graded evidence, and trust binds to guild-scoped GKN standing VERIFIES;
  * a fulfillment with no evidence is REJECTED (LN-005);
  * a fulfillment whose receipt is missing / does not resolve on the spine is REJECTED (AC-1);
  * a trust binding that carries a raw popularity scalar is REJECTED (feed/vanity model);
  * a trust binding whose standing_ref is not a guild-scoped GKN standing is REJECTED (LN-009);
  * an E3+ evidence packet with no null hypotheses is REJECTED (metadata-standards);
  * a hidden-compensation request is REJECTED (LN-004);
  * a broken chain link (response not pointing at the request) is REJECTED;
  * tampering the spine after receipting breaks verification.
"""
from __future__ import annotations

import copy
import os
import sys
import tempfile
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
sys.path.insert(0, PKG)

from labor_contract import (  # noqa: E402
    Evidence, Fulfillment, LaborChain, LaborContractError, LaborRequest, LaborResponse, TrustBinding,
    run_labor_loop, verify_labor_chain,
)

_passed = _failed = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global _passed, _failed
    if cond:
        _passed += 1; print(f"  ok   {name}")
    else:
        _failed += 1; print(f"  FAIL {name} :: {detail}")


def rejects(name: str, code: str, fn) -> None:
    try:
        fn()
        check(name, False, f"expected rejection {code}, none raised")
    except LaborContractError as e:
        check(name, e.code == code, f"expected {code}, got {e.code}")


def make_chain() -> LaborChain:
    """A canonical, valid request-centric loop (unreceipted; run_labor_loop stamps the receipts)."""
    return LaborChain(
        request=LaborRequest(
            request_id="labor-request:va-oit/rfp-portfolio-audit-001",
            requester="user:charles",
            request_type="RFP",
            objective="Independent audit of the VA OIT portfolio operating system.",
            compensation_disclosed=True,
            schedule="6 weeks",
            deadline="2026-09-15T00:00:00Z",
            evaluation_criteria=[
                {"criterion": "relevant_domain_evidence", "weight": 0.30},
                {"criterion": "execution_competence", "weight": 0.25},
                {"criterion": "availability_fit", "weight": 0.15},
                {"criterion": "understanding_clarity", "weight": 0.15},
                {"criterion": "reliability_fulfillment", "weight": 0.10},
                {"criterion": "compensation_terms_fit", "weight": 0.05},
            ],
        ),
        response=LaborResponse(
            response_id="labor-response:va-oit/rfp-portfolio-audit-001/team-sherlock",
            request_ref="labor-request:va-oit/rfp-portfolio-audit-001",
            responder="team:sherlock-auditors",
            approach="Provenance-first audit over the receipt spine with counter-tests.",
            terms="Fixed scope, milestone billing.",
            proposed_pricing="fixed:USD",
            is_team_bid=True,
        ),
        evidence=[
            Evidence(
                evidence_id="labor-evidence:va-oit/audit-methodology",
                response_ref="labor-response:va-oit/rfp-portfolio-audit-001/team-sherlock",
                artifact_refs=["ledger:seq:4021", "gkn:cred:sherlock-forensics-mastery-02"],
                evidence_grade="E4",
                null_hypothesis_ids=["nh:audit-bias", "nh:selection-effect"],
            ),
        ],
        fulfillment=Fulfillment(
            fulfillment_id="labor-fulfillment:va-oit/rfp-portfolio-audit-001",
            award_ref="labor-response:va-oit/rfp-portfolio-audit-001/team-sherlock",
            evidence_refs=["labor-evidence:va-oit/audit-methodology"],
            milestones=[{"id": "m1", "proof_ref": "ledger:seq:4055", "approved": True}],
            completion_status="delivered",
        ),
        trust=TrustBinding(
            trust_id="labor-trust:va-oit/rfp-portfolio-audit-001/completion",
            subject="team:sherlock-auditors",
            fulfillment_ref="labor-fulfillment:va-oit/rfp-portfolio-audit-001",
            event_type="completion",
            standing_ref="gkn:standing:guild:forensics:agent:sherlock-scout",
        ),
    )


def main() -> int:
    with tempfile.TemporaryDirectory() as d:
        ledger = Path(d) / "spine.jsonl"

        # --- happy path: run the loop, receipting every stage, then verify -------------------------
        chain = run_labor_loop(make_chain(), ledger)
        rec = verify_labor_chain(chain, ledger)
        check("valid request-centric loop verifies", rec["verified"] and rec["stages_receipted"] == 5)
        check("every stage carries a spine receipt",
              all(x.receipt_ref for x in [chain.request, chain.response, chain.fulfillment, chain.trust])
              and all(e.receipt_ref for e in chain.evidence))
        check("trust binds to guild-scoped GKN standing",
              rec["standing_ref"] == "gkn:standing:guild:forensics:agent:sherlock-scout")

        # --- LN-005: fulfillment with no evidence is REJECTED --------------------------------------
        c = run_labor_loop(make_chain(), Path(d) / "s2.jsonl")
        c.fulfillment.evidence_refs = []
        rejects("no-evidence fulfillment rejected (LN-005)", "no-evidence",
                lambda: verify_labor_chain(c, Path(d) / "s2.jsonl"))

        # --- AC-1: fulfillment with no receipt is REJECTED ----------------------------------------
        c = run_labor_loop(make_chain(), Path(d) / "s3.jsonl")
        c.fulfillment.receipt_ref = None
        rejects("receiptless fulfillment rejected (AC-1)", "receipt-required",
                lambda: verify_labor_chain(c, Path(d) / "s3.jsonl"))

        # --- AC-1: a forged receipt ref that does not resolve on the spine is REJECTED ------------
        c = run_labor_loop(make_chain(), Path(d) / "s3b.jsonl")
        c.fulfillment.receipt_ref = {"ledger_seq": 999, "entry_hash": "sha256:" + "0" * 64}
        rejects("unresolved receipt rejected (AC-1)", "receipt-unresolved",
                lambda: verify_labor_chain(c, Path(d) / "s3b.jsonl"))

        # --- charter core: raw popularity scalar in trust is REJECTED -----------------------------
        c = run_labor_loop(make_chain(), Path(d) / "s4.jsonl")
        c.trust.extra = {"followers": 24000, "score": 98}
        rejects("vanity scalar in trust rejected (feed model)", "vanity-scalar",
                lambda: verify_labor_chain(c, Path(d) / "s4.jsonl"))

        # --- LN-009: trust that is not a guild-scoped GKN standing is REJECTED ---------------------
        c = run_labor_loop(make_chain(), Path(d) / "s5.jsonl")
        c.trust.standing_ref = "0.97"  # a raw scalar masquerading as trust
        rejects("global/scalar standing_ref rejected (LN-009)", "trust-not-standing",
                lambda: verify_labor_chain(c, Path(d) / "s5.jsonl"))
        c = run_labor_loop(make_chain(), Path(d) / "s5b.jsonl")
        c.trust.standing_ref = "gkn:standing:global:user:alice"  # global, not guild-scoped
        rejects("non-guild-scoped standing_ref rejected", "trust-not-standing",
                lambda: verify_labor_chain(c, Path(d) / "s5b.jsonl"))

        # --- metadata-standards: E3+ evidence with no null hypotheses is REJECTED ------------------
        c = run_labor_loop(make_chain(), Path(d) / "s6.jsonl")
        c.evidence[0].null_hypothesis_ids = []
        rejects("E3+ evidence w/o null hypotheses rejected", "null-hypotheses-required",
                lambda: verify_labor_chain(c, Path(d) / "s6.jsonl"))

        # --- LN-004: hidden-compensation request is REJECTED --------------------------------------
        c = run_labor_loop(make_chain(), Path(d) / "s7.jsonl")
        c.request.compensation_disclosed = False
        rejects("hidden-compensation request rejected (LN-004)", "compensation-hidden",
                lambda: verify_labor_chain(c, Path(d) / "s7.jsonl"))
        # ... but an explicitly-typed volunteer/exploratory exemption is allowed
        c = run_labor_loop(make_chain(), Path(d) / "s7b.jsonl")
        c.request.compensation_disclosed = False
        c.request.comp_exempt = True
        # re-emit trust receipt after mutating request is unnecessary; comp is a request-level check
        check("comp-exempt request allowed (LN-004 exemption)",
              verify_labor_chain(c, Path(d) / "s7b.jsonl")["verified"])

        # --- chain integrity: response not pointing at the request is REJECTED ---------------------
        c = run_labor_loop(make_chain(), Path(d) / "s8.jsonl")
        c.response.request_ref = "labor-request:some/other-request"
        rejects("broken chain link rejected", "chain-broken",
                lambda: verify_labor_chain(c, Path(d) / "s8.jsonl"))

        # --- tamper: mutating the spine after receipting breaks verification -----------------------
        tl = Path(d) / "s9.jsonl"
        c = run_labor_loop(make_chain(), tl)
        lines = tl.read_text().splitlines()
        lines[0] = lines[0].replace("request", "req;;est", 1)
        tl.write_text("\n".join(lines) + "\n")
        rejects("spine tamper breaks verification", "spine-corrupt",
                lambda: verify_labor_chain(c, tl))

    print(f"\n{_passed} passed, {_failed} failed")
    return 1 if _failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
