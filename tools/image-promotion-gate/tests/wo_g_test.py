"""WO-G conformance — `python3 tests/wo_g_test.py` (no pytest dep).

Teeth BOTH ways (ADR-0001 WO-G; SourceOS Image Validation Corpus §"Promotion gate"):
  - a COMPLETE passing bundle promotes: emits a ProofArtifact on the shared spine, the chain verifies,
    the run package REPLAYS, and a linked ZonePromotion custody event is recorded;
  - a bundle MISSING ANY required category (or with a category explicitly failed) is REFUSED: nothing is
    promoted (no ProofArtifact), a PolicyException custody event is recorded, and PromotionRefused raises;
  - AC-1 (receipt law): a passing gate that cannot emit a receipt is NOT a promotion (fail-closed);
  - an explicit approved waiver ⇒ PASS-WITH-EXPLICIT-WAIVER promotes; an UNAPPROVED violation refuses;
  - fail-closed default: a required category with no evaluator refuses.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
sys.path.insert(0, PKG)
sys.path.insert(0, os.path.join(os.path.dirname(PKG), "proof-artifact-spine"))

from promotion_gate import (  # noqa: E402
    DEFAULT_REQUIRED, EvidenceBundle, GatePolicy, JUDGMENT_FAIL, JUDGMENT_PASS, JUDGMENT_WAIVER,
    PromotionRefused, evaluate_gate, promote,
)
from proof_artifact import verify_ledger  # noqa: E402
from publish import replay  # noqa: E402

_passed = _failed = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global _passed, _failed
    if cond:
        _passed += 1; print(f"  ok   {name}")
    else:
        _failed += 1; print(f"  FAIL {name} :: {detail}")


def _count_records(ledger: Path, record_type: str) -> int:
    import json
    n = 0
    if not ledger.exists():
        return 0
    for line in ledger.read_text().splitlines():
        line = line.strip()
        if line and json.loads(line).get("recordType") == record_type:
            n += 1
    return n


def _has_event(ledger: Path, event_type: str, image_ref: str) -> bool:
    import json
    if not ledger.exists():
        return False
    for line in ledger.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        e = json.loads(line)
        if e.get("recordType") == "CustodyEvent" and e.get("eventType") == event_type and e.get("artifactId") == image_ref:
            return True
    return False


def good_bundle(**over) -> EvidenceBundle:
    base = dict(
        image_ref="sourceos-desktop-x86_64:1.4",
        build_manifest={
            "completed": True, "build_id": "b-1041",
            "provenance": {
                "source_revision": "abc123", "package_manifest": "sha256:pm", "policy_manifest": "sha256:pol",
                "sbom": "sha256:sbom", "config_digest": "sha256:cfg",
            },
        },
        static_results={"passed": True, "checks": {"schema": "ok", "secrets": "clean", "baseline": "ok"}},
        dynamic_scenarios=[
            {"id": "boot-login", "required": True, "passed": True, "replay_ref": "as://run/1"},
            {"id": "network", "required": True, "passed": True},
            {"id": "dev-path", "required": False, "passed": True},
        ],
        policy_violations=[],
        red_team={"required": True, "passed": True},
        blue_team={"required": True, "passed": True},
        replay_ref="proofpack://bundle/1041",
        approvals=[{"approver": "mdheller", "role": "release-manager"}],
    )
    base.update(over)
    return EvidenceBundle(**base)


def main() -> int:
    with tempfile.TemporaryDirectory() as d:
        # ── HAPPY PATH: complete bundle promotes, receipts, replays ──────────────────────────────────
        ledger = Path(d) / "spine.jsonl"
        rep = evaluate_gate(good_bundle())
        check("complete bundle judged PASS", rep.judgment == JUDGMENT_PASS, str(rep.reason_codes))

        receipt = promote(good_bundle(), ledger)
        check("promotion emits a ProofArtifact", receipt["recordType"] == "ProofArtifact")
        check("receipt marks image extent", receipt["extent"] == "images/sourceos-desktop-x86_64:1.4")
        check("receipt is Measured level", receipt["epistemicLevel"] == "Measured")
        check("gate report says promoted", receipt["_gateReport"]["promoted"] is True)

        ok, msg = verify_ledger(ledger)
        check("spine chain verifies after promotion", ok, msg)

        rp = replay(receipt)
        check("promotion run package replays", rp["verified"] and "build_completed" in rp["plan"])
        check("replay carries evidence bundle", rp["outputs"][0]["evidence_bundle"]["image_ref"] == "sourceos-desktop-x86_64:1.4")

        check("ZonePromotion custody event recorded", _has_event(ledger, "ZonePromotion", "sourceos-desktop-x86_64:1.4"))
        check("one ProofArtifact on the spine", _count_records(ledger, "ProofArtifact") == 1)

        # ── TEETH: a bundle missing EACH required category is refused, nothing promotes ──────────────
        drops = {
            "build_completed":            dict(build_manifest={"completed": False, "provenance": good_bundle().build_manifest["provenance"]}),
            "provenance_manifest":        dict(build_manifest={"completed": True, "build_id": "b", "provenance": {"source_revision": "x"}}),
            "static_validation":          dict(static_results={"passed": False, "checks": {"secrets": "LEAK"}}),
            "dynamic_scenarios":          dict(dynamic_scenarios=[{"id": "boot", "required": True, "passed": False}]),
            "no_unapproved_violations":   dict(policy_violations=[{"id": "CVE-x", "severity": "high", "approved": False}]),
            "replay_ref":                 dict(replay_ref=""),
            "red_blue_smoke":             dict(blue_team={"required": True, "passed": False}),
            "approvals":                  dict(approvals=[{"approver": "bot", "role": "ci"}]),
        }
        for cat, override in drops.items():
            led = Path(d) / f"refuse-{cat}.jsonl"
            b = good_bundle(**override)
            try:
                promote(b, led)
                check(f"refused when {cat} fails", False, "promotion succeeded — should have refused")
            except PromotionRefused as e:
                refused = e.report.judgment == JUDGMENT_FAIL
                no_proof = _count_records(led, "ProofArtifact") == 0
                has_pe = _has_event(led, "PolicyException", b.image_ref)
                check(f"refused when {cat} fails (no promotion + PolicyException)",
                      refused and no_proof and has_pe,
                      f"judgment={e.report.judgment} proofs={_count_records(led,'ProofArtifact')} pe={has_pe}")

        # ── evidence_bundle_complete: an empty bundle is refused as incomplete ──────────────────────
        led = Path(d) / "empty.jsonl"
        try:
            promote(EvidenceBundle(image_ref="img:0"), led)
            check("empty bundle refused as incomplete", False, "promoted an empty bundle")
        except PromotionRefused as e:
            check("empty bundle refused as incomplete",
                  "evidence_bundle_complete" in e.report.reason_codes and _count_records(led, "ProofArtifact") == 0,
                  str(e.report.reason_codes))

        # ── AC-1: passing gate but unwritable ledger ⇒ NOT a promotion (fail-closed) ────────────────
        bad_ledger = Path(d) / "nope" / "deep" / "spine.jsonl"   # parent dir does not exist
        try:
            promote(good_bundle(), bad_ledger)
            check("AC-1: no receipt ⇒ no promotion", False, "promoted with no writable ledger")
        except PromotionRefused as e:
            check("AC-1: no receipt ⇒ no promotion",
                  any("receipt-required" in rc for rc in e.report.reason_codes), str(e.report.reason_codes))
        check("AC-1: nothing written when receipt fails", not bad_ledger.exists())

        # ── WAIVER: an explicitly APPROVED violation ⇒ PASS-WITH-EXPLICIT-WAIVER promotes ───────────
        led = Path(d) / "waiver.jsonl"
        wb = good_bundle(policy_violations=[{"id": "baseline-exception-7", "severity": "low", "approved": True}])
        rw = promote(wb, led)
        check("approved waiver promotes with PASS-WITH-EXPLICIT-WAIVER",
              rw["_gateReport"]["judgment"] == JUDGMENT_WAIVER and _count_records(led, "ProofArtifact") == 1,
              rw["_gateReport"]["judgment"])
        # same violation, waivers disabled by policy ⇒ refused
        led2 = Path(d) / "nowaiver.jsonl"
        try:
            promote(wb, led2, policy=GatePolicy(allow_waivers=False))
            check("waivers-disabled policy refuses approved-violation bundle", False, "promoted despite disabled waivers")
        except PromotionRefused:
            check("waivers-disabled policy refuses approved-violation bundle", _count_records(led2, "ProofArtifact") == 0)

        # ── fail-closed: a required category with no evaluator refuses ──────────────────────────────
        led3 = Path(d) / "unknowncat.jsonl"
        pol = GatePolicy(required_categories=frozenset(DEFAULT_REQUIRED | {"cloudshell_reachability"}))
        try:
            promote(good_bundle(), led3, policy=pol)
            check("required category with no evaluator refuses (fail-closed)", False, "promoted with unprovable category")
        except PromotionRefused as e:
            check("required category with no evaluator refuses (fail-closed)",
                  "cloudshell_reachability" in e.report.reason_codes and _count_records(led3, "ProofArtifact") == 0,
                  str(e.report.reason_codes))

        # ── tamper detection on a promotion ledger ──────────────────────────────────────────────────
        lines = ledger.read_text().splitlines()
        lines[0] = lines[0].replace("sourceos-desktop", "backdoored")
        ledger.write_text("\n".join(lines) + "\n")
        okt, msgt = verify_ledger(ledger)
        check("tamper on a promotion breaks the chain", not okt, msgt)

    print(f"\n{_passed} passed, {_failed} failed")
    return 1 if _failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
