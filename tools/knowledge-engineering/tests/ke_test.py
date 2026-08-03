"""KnowledgeEngineeringWorkspace conformance — `python3 tools/knowledge-engineering/tests/ke_test.py`.

No pytest, stdlib only. Teeth BOTH ways: every examples/*.valid.json conforms; every examples/*.invalid.json
is rejected; each cross-field guard (KE-T1..KE-T9) fires individually on a targeted mutation of a valid
workspace — so a guard that silently stops biting is caught here, not in production. Plus: resolve_active
returns the max-version active entry (human overwrite wins, prior retained) and the receipt spine
(proof-artifact-spine) actually seals + verifies a KE promotion/authorship receipt.
"""
from __future__ import annotations

import copy
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
sys.path.insert(0, PKG)

import validate_ke_workspace as V  # noqa: E402
import ke_receipts as R  # noqa: E402

_passed = _failed = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global _passed, _failed
    if cond:
        _passed += 1
        print(f"  ok   {name}")
    else:
        _failed += 1
        print(f"  FAIL {name} :: {detail}")


def _load(name: str) -> dict:
    with open(os.path.join(PKG, "examples", name), encoding="utf-8") as fh:
        return json.load(fh)


def rejects(record: dict) -> bool:
    try:
        V.validate_ke_workspace(record)
        return False
    except V.ValidationError:
        return True


def main() -> int:
    ex_dir = os.path.join(PKG, "examples")
    files = sorted(f for f in os.listdir(ex_dir) if f.endswith(".json"))
    valids = [f for f in files if f.endswith(".valid.json")]
    invalids = [f for f in files if f.endswith(".invalid.json")]

    # schema exercised (drift guard)
    try:
        V.validate_schema(json.loads(open(V.SCHEMA, encoding="utf-8").read()))
        check("schema exercised (no drift)", True)
    except V.ValidationError as exc:
        check("schema exercised (no drift)", False, str(exc))

    for f in valids:
        try:
            V.validate_ke_workspace(_load(f))
            check(f"valid: {f}", True)
        except V.ValidationError as exc:
            check(f"valid: {f}", False, str(exc))

    for f in invalids:
        check(f"invalid rejected: {f}", rejects(_load(f)))

    check("fixture counts (2 valid, 13 invalid)", len(valids) == 2 and len(invalids) == 13,
          f"got {len(valids)} valid / {len(invalids)} invalid")

    # --- per-tooth mutation: start from a valid workspace and make each guard fire on its own ---
    base = _load("governed-workspace.valid.json")
    human = _load("human-authoring.valid.json")

    # KE-T1 learn-don't-match: static_match dictionary mode
    m = copy.deepcopy(base); m["spec"]["dictionaries"][0]["mode"] = "static_match"
    check("KE-T1 static-match dictionary rejected", rejects(m))
    # KE-T1: no sourceAnchor => bare word/tag
    m = copy.deepcopy(base); del m["spec"]["dictionaries"][0]["entries"][0]["sourceAnchor"]
    check("KE-T1 no-source-anchor rejected", rejects(m))
    # KE-T1: learned provenance without a learned predictor (static membership)
    m = copy.deepcopy(base)
    m["spec"]["dictionaries"][0]["entries"][0]["provenance"] = {
        "class": "learned", "receiptRef": base["spec"]["versions"][0]["receiptRef"]}
    check("KE-T1 learned-without-predictor rejected", rejects(m))
    # KE-T1: lifecycle skip (promoted past review with unreviewed anchor)
    m = copy.deepcopy(base); e = m["spec"]["dictionaries"][0]["entries"][0]
    e["promotionState"] = "operational_definition"; e["sourceAnchor"]["reviewState"] = "unreviewed"
    check("KE-T1 lifecycle-skip rejected", rejects(m))

    # KE-T2 type not in governed registry
    m = copy.deepcopy(base); m["spec"]["entityTypes"][0]["registryRef"]["member"] = "WIDGET"
    check("KE-T2 type-not-in-registry rejected", rejects(m))
    m = copy.deepcopy(base)
    m["spec"]["entityTypes"][0]["registryRef"]["schemaId"] = "https://evil.example/types.json"
    check("KE-T2 unknown-registry rejected", rejects(m))

    # KE-T3 rule dangling ref
    m = copy.deepcopy(base); m["spec"]["rules"][0]["relationTypeRefs"] = ["rt:ghost"]
    check("KE-T3 rule-dangling-ref rejected", rejects(m))

    # KE-T4 promotion with no receipt
    m = copy.deepcopy(base); m["spec"]["annotations"][0]["promotionReceiptRef"] = None
    check("KE-T4 promotion-no-receipt rejected", rejects(m))

    # KE-T5 overwrite without supersedes
    m = copy.deepcopy(human); m["spec"]["authorship"][0]["supersedes"] = None
    check("KE-T5 overwrite-no-supersedes rejected", rejects(m))

    # KE-T6 authorship missing author / receipt
    m = copy.deepcopy(human); del m["spec"]["authorship"][0]["author"]
    check("KE-T6 authorship-no-author rejected", rejects(m))
    m = copy.deepcopy(human); del m["spec"]["authorship"][0]["receiptRef"]
    check("KE-T6 authorship-no-receipt rejected", rejects(m))

    # KE-T7 two active versions of the same conceptRef
    m = copy.deepcopy(human); m["spec"]["dictionaries"][0]["entries"][0]["status"] = "approved"
    check("KE-T7 two-active-versions rejected", rejects(m))

    # KE-T8 bad receipt format (version)
    m = copy.deepcopy(base); m["spec"]["versions"][0]["receiptRef"] = "deadbeef"
    check("KE-T8 bad-receipt-format rejected", rejects(m))

    # KE-T9 oversized text doc
    m = copy.deepcopy(base); m["spec"]["documentSet"][0]["wordCount"] = 5000
    check("KE-T9 oversized-doc rejected", rejects(m))

    # --- resolve_active: the human overwrite wins; prior learned version retained but not active ---
    entry, cls = V.resolve_active(human, "systema:concept:contact-lists")
    check("resolve_active returns max-version entry", entry is not None and entry.get("version") == 2,
          f"got {entry and entry.get('version')}")
    check("resolve_active returns human_authored provenance class", cls == "human_authored", str(cls))
    prior = [e for d in human["spec"]["dictionaries"] for e in d["entries"] if e.get("version") == 1]
    check("prior learned version retained (superseded, not deleted)",
          len(prior) == 1 and prior[0]["status"] == "superseded")

    # --- receipt spine (consume proof-artifact-spine): a KE receipt is chained + verifiable ---
    with tempfile.TemporaryDirectory() as td:
        ledger = os.path.join(td, "ke-ledger.jsonl")
        r1 = R.receipt_promotion(ledger, annotation_id="anno:utt-0007:tok-3",
                                 target_kind="dictionary_term", ref="systema:concept:contact-lists")
        r2 = R.receipt_authorship(ledger, event_id="ke:auth:0001", op="overwrite",
                                  target_ref="systema:concept:contact-lists", author="@mdheller",
                                  version=2, supersedes="systema:concept:contact-lists@1")
        check("promotion receipt is a valid ReceiptRef", bool(V._RECEIPT.match(r1["entryHash"])))
        check("authorship receipt chains to promotion", r2["ledgerPrevHash"] == r1["entryHash"])
        ok, msg = R.PA.verify_ledger(ledger)
        check("receipt ledger verifies (tamper-evident)", ok, msg)

    print(f"\n{_passed} passed, {_failed} failed")
    return 1 if _failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
