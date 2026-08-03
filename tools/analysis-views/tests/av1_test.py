"""AV-1 conformance — `python3 tools/analysis-views/tests/av1_test.py` (no pytest).

Teeth BOTH ways: every examples/*.valid.json conforms; every examples/*.invalid.json is rejected; and
each of the seven cross-field guards (AV-T1..AV-T7) fires individually on a targeted mutation of a valid
descriptor (so a guard that silently stops biting is caught).
"""
from __future__ import annotations

import copy
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
sys.path.insert(0, PKG)

import validate_analysis_view as V  # noqa: E402

_passed = _failed = 0


def check(name, cond, detail=""):
    global _passed, _failed
    if cond:
        _passed += 1; print(f"  ok   {name}")
    else:
        _failed += 1; print(f"  FAIL {name} :: {detail}")


def _load(name):
    return json.loads((os.path.join(PKG, "examples", name)) and open(os.path.join(PKG, "examples", name)).read())


def main() -> int:
    schema = json.loads(open(V.SCHEMA).read())
    ex_dir = os.path.join(PKG, "examples")
    files = sorted(f for f in os.listdir(ex_dir) if f.endswith(".json"))

    valids = [f for f in files if f.endswith(".valid.json")]
    invalids = [f for f in files if f.endswith(".invalid.json")]
    check("fixtures present", len(valids) >= 3 and len(invalids) >= 6, f"{len(valids)} valid / {len(invalids)} invalid")

    # every valid conforms
    for f in valids:
        errs = V.validate_record(_load(f), schema, f)
        check(f"valid conforms: {f}", errs == [], "; ".join(errs))

    # every invalid is rejected
    for f in invalids:
        errs = V.validate_record(_load(f), schema, f)
        check(f"invalid rejected: {f}", errs != [], "expected rejection, got none")

    # each of the 12 model kinds path: base a valid LSA descriptor for targeted mutations
    base = _load("lsa-corpus-view.valid.json")
    check("base is valid before mutation", V.validate_record(base, schema, "base") == [])

    def fires(tag, mutate):
        rec = copy.deepcopy(base)
        mutate(rec)
        errs = V.validate_record(rec, schema, tag)
        return any(tag_id in e for e in errs for tag_id in [tag])

    # AV-T1: give the LSA view an LSI param
    def m1(r): r["transform"]["rank"] = 256
    check("AV-T1 fires (LSA carrying rank)", fires("AV-T1", m1))

    # AV-T2: keep output_hash but break reconstruction
    def m2(r): r["lifecycle"]["reconstruction"]["from_seed"] = False
    check("AV-T2 fires (hash without pinned reconstruction)", fires("AV-T2", m2))

    # AV-T3: scramble zone order
    def m3(r): r["governance"]["zone_path"] = ["Examination", "Landing"]
    check("AV-T3 fires (zone_path descending)", fires("AV-T3", m3))

    # AV-T4: push to Governed without signing
    def m4(r):
        r["governance"]["zone_path"] = ["Landing", "Examination", "Integration", "Governed"]
        r["integrity"]["signed"] = False
    check("AV-T4 fires (governed unsigned)", fires("AV-T4", m4))

    # AV-T5: external origin over Derived
    def m5(r):
        r["governance"]["provenance"]["origin"] = "external"
        r["governance"]["access"]["epistemic_ceiling"] = "Measured"
    check("AV-T5 fires (external over Derived)", fires("AV-T5", m5))

    # AV-T6: expansion without full coverage
    def m6(r):
        r["transform"]["expansion"] = {"kind": "topic_split", "from": 512, "to": 528}
        r["coverage"] = {"ratio": 0.5}
        r["stability"] = {"npmi": 0.1}
    check("AV-T6 fires (expansion under-covered)", fires("AV-T6", m6))

    # AV-T7: deterministic reconstruction with no source refs
    def m7(r): r["lifecycle"]["reconstruction"]["source_refs"] = []
    check("AV-T7 fires (reconstruct from nothing)", fires("AV-T7", m7))

    # positive control: the emergence gate ADMITS a fully-fibered expansion (teeth don't over-bite)
    ok_expand = _load("lsi-governed-expansion.valid.json")
    check("AV-T6 admits fully-fibered expansion", V.validate_record(ok_expand, schema, "expand") == [])

    print(f"\n{_passed} passed, {_failed} failed")
    return 1 if _failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
