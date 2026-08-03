"""SourceOS image validation promotion gate — WO-G of ADR-0001 (Open Agent Continuum).

The law (SourceOS Image Generation & Validation Corpus §"Promotion gate"; ADR-0001 §7): an image build
may update Git / close its issue ONLY if it passes the promotion gate. Shipping an image is a `publish`
(`f_!`) in the adjunction (ADR-0001 §3) — so it obeys **AC-1, the receipt law**: a promotion that cannot
emit a receipt is not a promotion.

The key identification (ADR-0001 §3, §8 WO-G): **the EvidenceBundle IS a ProofArtifact.** We do not invent
a second provenance store — the gate emits its promotion receipt onto the SAME hash-chained, FIPS-approved
(SHA-256) receipt spine used by every other `publish` (`tools/proof-artifact-spine`), and its failure onto
the SAME spine as a 14-type CustodyEvent (`PolicyException`). One spine, both record types.

Behaviour (fail-closed):
  - `evaluate_gate(bundle, policy)` — pure verdict: each REQUIRED category is PASS / FAIL / WAIVED. A
    required category that cannot be evaluated (its evidence is absent) is FAIL, never skipped. ANY required
    category not satisfied ⇒ overall FAIL. This is the teeth: a bundle missing a required category is
    refused, exactly like one whose category explicitly failed.
  - `promote(bundle, policy, ledger, agent)`:
        PASS ⇒ emit a ProofArtifact (via the WO-B `publish` = `f_!` path) recording the promotion, plus a
               `ZonePromotion` CustodyEvent linking it; return the receipt. The image may now update Git.
        FAIL ⇒ emit a `PolicyException` CustodyEvent (reason codes in the note) and raise
               `PromotionRefused`. No ProofArtifact is written; nothing is promoted; Git is NOT updated.

A passing promotion is a `Measured`-level publish: the evidence-grade ladder (MS-P6) maps E4 Authenticated
(hash verified, chain intact) → Measured — which is precisely a complete, replayable, hash-bound bundle.

Self-contained: stdlib + `blake3` (pulled in transitively by the spine's dual-hash). Run the conformance
test with `python3 tests/wo_g_test.py`.
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

# Reuse the receipt spine (WO-B) + the 14-type CustodyEvent model (MS-P4). One spine, no fork.
_SPINE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "proof-artifact-spine")
if _SPINE not in sys.path:
    sys.path.insert(0, _SPINE)

from custody_event import emit_custody_event  # noqa: E402
from proof_artifact import RunPackage, canonical  # noqa: E402
from publish import PublishDenied, PublishRequest, publish  # noqa: E402

# ── The promotion-gate categories (Corpus §"Promotion gate before Git update / task closure") ──────────
# Each is a named requirement the EvidenceBundle must satisfy. The default policy REQUIRES the core set the
# WO-G work order names; the remaining corpus categories (cloudshell / sensor-refresh / retrieval-freshness)
# are supported as OPTIONAL extra categories via GatePolicy.required_categories so the gate is extensible
# without a code change.
BUILD_COMPLETED = "build_completed"
PROVENANCE_MANIFEST = "provenance_manifest"
STATIC_VALIDATION = "static_validation"
DYNAMIC_SCENARIOS = "dynamic_scenarios"
NO_UNAPPROVED_VIOLATIONS = "no_unapproved_policy_violations"
EVIDENCE_BUNDLE_COMPLETE = "evidence_bundle_complete"
REPLAY_REF = "replay_ref"
RED_BLUE_SMOKE = "red_blue_smoke"
APPROVALS = "approvals"

# The default required set — the WO-G core. Fail-closed over exactly these unless the policy overrides.
DEFAULT_REQUIRED = frozenset({
    BUILD_COMPLETED, PROVENANCE_MANIFEST, STATIC_VALIDATION, DYNAMIC_SCENARIOS,
    NO_UNAPPROVED_VIOLATIONS, EVIDENCE_BUNDLE_COMPLETE, REPLAY_REF, RED_BLUE_SMOKE, APPROVALS,
})

# Provenance manifest MUST carry these digests (Corpus §"Emit provenance": build manifest, source
# revision, package manifest, policy manifest, SBOM, config digest).
REQUIRED_PROVENANCE_KEYS = ("source_revision", "package_manifest", "policy_manifest", "sbom", "config_digest")

PASS = "PASS"
FAIL = "FAIL"
WAIVED = "WAIVED"

JUDGMENT_PASS = "PASS"
JUDGMENT_WAIVER = "PASS-WITH-EXPLICIT-WAIVER"
JUDGMENT_FAIL = "FAIL"


class PromotionRefused(Exception):
    """Raised when the gate denies promotion. Carries the GateReport so the caller can open remediation."""
    def __init__(self, report: "GateReport"):
        super().__init__(f"promotion refused: {report.judgment} — {report.reason_codes}")
        self.report = report


@dataclass
class EvidenceBundle:
    """The image build's evidence bundle (Corpus §"Evidence bundle schema"). This is the object the gate
    hashes into the ProofArtifact — the bundle IS the receipted artifact."""
    image_ref: str                                  # what is being promoted, e.g. sourceos-desktop-x86_64:1.4
    build_manifest: dict = field(default_factory=dict)      # {completed: bool, provenance: {...}, build_id}
    static_results: dict = field(default_factory=dict)      # {passed: bool, checks: {...}}
    dynamic_scenarios: list[dict] = field(default_factory=list)  # [{id, required, passed, replay_ref?}]
    policy_violations: list[dict] = field(default_factory=list)  # [{id, severity, approved: bool}]
    red_team: dict = field(default_factory=dict)            # {required: bool, passed: bool}
    blue_team: dict = field(default_factory=dict)           # {required: bool, passed: bool}
    replay_ref: str = ""                                    # bundle-level replay reference (proof-pack uri)
    approvals: list[dict] = field(default_factory=list)     # [{approver, role}]

    def summary(self) -> dict:
        """Deterministic, hashable projection of the bundle — the exact bytes bound into the receipt's
        inputHash. Sorted collections so two equal bundles hash identically."""
        return {
            "image_ref": self.image_ref,
            "build_manifest": self.build_manifest,
            "static_results": self.static_results,
            "dynamic_scenarios": self.dynamic_scenarios,
            "policy_violations": self.policy_violations,
            "red_team": self.red_team,
            "blue_team": self.blue_team,
            "replay_ref": self.replay_ref,
            "approvals": self.approvals,
        }


@dataclass
class GatePolicy:
    """What THIS gate demands. Fail-closed over `required_categories`."""
    required_categories: frozenset[str] = DEFAULT_REQUIRED
    required_approver_roles: frozenset[str] = frozenset({"release-manager"})
    min_required_scenarios: int = 1        # at least this many REQUIRED dynamic scenarios must pass
    allow_waivers: bool = True             # permit PASS-WITH-EXPLICIT-WAIVER for approved policy violations


@dataclass
class CategoryVerdict:
    category: str
    status: str        # PASS / FAIL / WAIVED
    detail: str = ""


@dataclass
class GateReport:
    image_ref: str
    verdicts: list[CategoryVerdict]
    judgment: str                          # PASS / PASS-WITH-EXPLICIT-WAIVER / FAIL
    reason_codes: list[str]                # the failing (or waived) categories — the "reason codes"
    promoted: bool = False

    def to_dict(self) -> dict:
        return {
            "image_ref": self.image_ref,
            "judgment": self.judgment,
            "reason_codes": self.reason_codes,
            "promoted": self.promoted,
            "verdicts": [{"category": v.category, "status": v.status, "detail": v.detail} for v in self.verdicts],
        }


# ── Per-category evaluators. Each returns (status, detail). Absence of evidence ⇒ FAIL (fail-closed). ──

def _v_build_completed(b: EvidenceBundle, p: GatePolicy) -> tuple[str, str]:
    if b.build_manifest.get("completed") is True:
        return PASS, f"build {b.build_manifest.get('build_id', '?')} completed"
    return FAIL, "build not completed (build_manifest.completed != True)"


def _v_provenance(b: EvidenceBundle, p: GatePolicy) -> tuple[str, str]:
    prov = b.build_manifest.get("provenance") or {}
    missing = [k for k in REQUIRED_PROVENANCE_KEYS if not prov.get(k)]
    if missing:
        return FAIL, f"provenance manifest missing {missing}"
    return PASS, "provenance manifest complete"


def _v_static(b: EvidenceBundle, p: GatePolicy) -> tuple[str, str]:
    if not b.static_results:
        return FAIL, "no static validation results"
    if b.static_results.get("passed") is True:
        return PASS, "static validation passed"
    return FAIL, f"static validation failed: {b.static_results.get('checks', {})}"


def _v_dynamic(b: EvidenceBundle, p: GatePolicy) -> tuple[str, str]:
    required = [s for s in b.dynamic_scenarios if s.get("required")]
    if len(required) < p.min_required_scenarios:
        return FAIL, f"only {len(required)} required scenarios, need >= {p.min_required_scenarios}"
    failed = [s.get("id", "?") for s in required if s.get("passed") is not True]
    if failed:
        return FAIL, f"required dynamic scenarios failed: {failed}"
    return PASS, f"{len(required)} required dynamic scenarios passed"


def _v_no_unapproved_violations(b: EvidenceBundle, p: GatePolicy) -> tuple[str, str]:
    unapproved = [v.get("id", "?") for v in b.policy_violations if v.get("approved") is not True]
    if unapproved:
        return FAIL, f"unapproved policy violations: {unapproved}"
    if b.policy_violations:  # all present violations are explicitly approved ⇒ waiver path
        if not p.allow_waivers:
            return FAIL, "approved violations present but waivers disabled by policy"
        return WAIVED, f"explicit waivers: {[v.get('id') for v in b.policy_violations]}"
    return PASS, "no policy violations"


def _v_evidence_complete(b: EvidenceBundle, p: GatePolicy) -> tuple[str, str]:
    """Structural completeness of the EvidenceBundle (Corpus §"Evidence completeness"). Empty required
    sub-artifacts ⇒ the bundle is incomplete ⇒ FAIL."""
    missing = []
    if not b.build_manifest:
        missing.append("build_manifest")
    if not b.static_results:
        missing.append("static_results")
    if not b.dynamic_scenarios:
        missing.append("dynamic_scenarios")
    if not b.replay_ref:
        missing.append("replay_ref")
    if not b.approvals:
        missing.append("approvals")
    if missing:
        return FAIL, f"evidence bundle incomplete: {missing}"
    return PASS, "evidence bundle complete"


def _v_replay_ref(b: EvidenceBundle, p: GatePolicy) -> tuple[str, str]:
    if b.replay_ref:
        return PASS, f"replay ref {b.replay_ref}"
    return FAIL, "no replay reference emitted"


def _v_red_blue(b: EvidenceBundle, p: GatePolicy) -> tuple[str, str]:
    for name, res in (("red", b.red_team), ("blue", b.blue_team)):
        if res.get("required"):
            if res.get("passed") is not True:
                return FAIL, f"{name}-team required smoke playbook not passed"
    if not b.red_team and not b.blue_team:
        return FAIL, "no red/blue smoke results present"
    return PASS, "required red/blue smoke playbooks passed"


def _v_approvals(b: EvidenceBundle, p: GatePolicy) -> tuple[str, str]:
    roles = {a.get("role") for a in b.approvals}
    missing = [r for r in p.required_approver_roles if r not in roles]
    if missing:
        return FAIL, f"missing required approvals from {missing}"
    return PASS, f"approvals satisfied ({sorted(roles)})"


_EVALUATORS = {
    BUILD_COMPLETED: _v_build_completed,
    PROVENANCE_MANIFEST: _v_provenance,
    STATIC_VALIDATION: _v_static,
    DYNAMIC_SCENARIOS: _v_dynamic,
    NO_UNAPPROVED_VIOLATIONS: _v_no_unapproved_violations,
    EVIDENCE_BUNDLE_COMPLETE: _v_evidence_complete,
    REPLAY_REF: _v_replay_ref,
    RED_BLUE_SMOKE: _v_red_blue,
    APPROVALS: _v_approvals,
}


def evaluate_gate(bundle: EvidenceBundle, policy: GatePolicy | None = None) -> GateReport:
    """Pure gate evaluation — no side effects. Fail-closed: an unknown required category, or a required
    category whose evidence is absent, is a FAIL (never skipped). ANY required category not satisfied ⇒
    overall judgment FAIL."""
    policy = policy or GatePolicy()
    verdicts: list[CategoryVerdict] = []
    reason_codes: list[str] = []
    any_waived = False
    any_failed = False

    for cat in sorted(policy.required_categories):
        evaluator = _EVALUATORS.get(cat)
        if evaluator is None:
            # A required category with no evaluator cannot be proven satisfied ⇒ fail-closed.
            verdicts.append(CategoryVerdict(cat, FAIL, "no evaluator for required category"))
            reason_codes.append(cat)
            any_failed = True
            continue
        status, detail = evaluator(bundle, policy)
        verdicts.append(CategoryVerdict(cat, status, detail))
        if status == FAIL:
            any_failed = True
            reason_codes.append(cat)
        elif status == WAIVED:
            any_waived = True
            reason_codes.append(cat)

    if any_failed:
        judgment = JUDGMENT_FAIL
    elif any_waived:
        judgment = JUDGMENT_WAIVER
    else:
        judgment = JUDGMENT_PASS

    return GateReport(image_ref=bundle.image_ref, verdicts=verdicts, judgment=judgment,
                      reason_codes=reason_codes)


def promote(
    bundle: EvidenceBundle,
    ledger: Path,
    *,
    policy: GatePolicy | None = None,
    agent: str = "sourceos-promotion-gate",
    actor_id: str = "image-promotion-gate",
) -> dict:
    """Evaluate the gate and act on the verdict, fail-closed.

    PASS / PASS-WITH-EXPLICIT-WAIVER ⇒ emit a ProofArtifact (the WO-B `publish` = `f_!` path) recording the
      promotion, plus a `ZonePromotion` CustodyEvent linking the receipt; return the receipt dict (with an
      added `_gateReport`). AC-1: if the receipt cannot be written, `publish` raises and NOTHING is promoted.

    FAIL ⇒ emit a `PolicyException` CustodyEvent (reason codes in the note) and raise `PromotionRefused`.
      No ProofArtifact is written. Git must not be updated; open/continue remediation.
    """
    policy = policy or GatePolicy()
    report = evaluate_gate(bundle, policy)
    ledger = Path(ledger)

    if report.judgment == JUDGMENT_FAIL:
        # Fail-closed: record the refusal on the spine as a PolicyException custody event, then refuse.
        # (Corpus §"Failure handling": do not update Git, record reason code, attach proof.)
        note = f"promotion refused for {bundle.image_ref}: reason_codes={report.reason_codes}"
        emit_custody_event(
            ledger,
            event_type="PolicyException",
            artifact_id=bundle.image_ref,
            actor_id=actor_id,
            actor_type="VerificationProcess",
            zone_from="Examination",   # blocked BEFORE entering the Governed (released) zone
            zone_to="Governed",
            note=note,
        )
        raise PromotionRefused(report)

    # PASS (possibly with explicit waiver): the promotion is a publish (f_!). The EvidenceBundle IS the
    # ProofArtifact — its summary is the inputHash-bound payload; the gate verdicts are the run package.
    run = RunPackage(
        plan=[v.category for v in report.verdicts],
        tool_calls=[{"category": v.category, "status": v.status, "detail": v.detail} for v in report.verdicts],
        outputs=[{"image_ref": bundle.image_ref, "judgment": report.judgment,
                  "evidence_bundle": bundle.summary()}],
        policy_report={"judgment": report.judgment, "reason_codes": report.reason_codes,
                       "policy_violations": bundle.policy_violations, "approvals": bundle.approvals,
                       "required_categories": sorted(policy.required_categories)},
    )
    req = PublishRequest(
        agent=agent,
        external=False,
        extent=f"images/{bundle.image_ref}",
        phase="promotion-gate",
        epistemic_level="Measured",   # E4 Authenticated → Measured (MS-P6 ladder): hash-verified, replayable
        inputs=canonical(bundle.summary()),
        run=run,
        cover=[bundle.image_ref],
        existing_covers=[],
    )
    try:
        receipt = publish(req, ledger)   # emits the ProofArtifact; AC-1 fail-closed inside publish()
    except PublishDenied as e:
        # No receipt ⇒ no promotion. Surface as a refusal (the gate passed, but the estate could not
        # record it, so per AC-1 it is not a promotion).
        report.judgment = JUDGMENT_FAIL
        report.reason_codes.append(f"receipt-required:{e.code}")
        raise PromotionRefused(report) from e

    # Link a ZonePromotion custody event to the promotion receipt (one spine, both record types).
    emit_custody_event(
        ledger,
        event_type="ZonePromotion",
        artifact_id=bundle.image_ref,
        actor_id=actor_id,
        actor_type="VerificationProcess",
        zone_from="Examination",
        zone_to="Governed",
        tool_name="image-promotion-gate",
        note=f"promotion receipt entryHash={receipt['entryHash']} judgment={report.judgment}",
    )

    report.promoted = True
    receipt = dict(receipt)
    receipt["_gateReport"] = report.to_dict()
    return receipt
