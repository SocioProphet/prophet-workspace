"""CSKGEdge conformance — `python3 tools/cskg-edge/tests/cskg_edge_test.py` (no pytest, stdlib only).

Teeth BOTH ways: every examples/*.valid.json conforms; every examples/*.invalid.json is rejected; and
each of the seven cross-field guards (CE-T1..CE-T7) fires individually on a targeted mutation of a valid
descriptor — so a guard that silently stops biting is caught here, not in production.
"""
from __future__ import annotations

import copy
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
sys.path.insert(0, PKG)

import validate_cskg_edge as V  # noqa: E402

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
        V.validate_cskg_edge(record)
        return False
    except V.ValidationError:
        return True


def main() -> int:
    ex_dir = os.path.join(PKG, "examples")
    files = sorted(f for f in os.listdir(ex_dir) if f.endswith(".json"))
    valids = [f for f in files if f.endswith(".valid.json")]
    invalids = [f for f in files if f.endswith(".invalid.json")]

    # schema is exercised (drift guard)
    try:
        V.validate_schema(json.loads(open(V.SCHEMA, encoding="utf-8").read()))
        check("schema exercised (no drift)", True)
    except V.ValidationError as exc:
        check("schema exercised (no drift)", False, str(exc))

    # every valid fixture passes
    for f in valids:
        try:
            V.validate_cskg_edge(_load(f))
            check(f"valid: {f}", True)
        except V.ValidationError as exc:
            check(f"valid: {f}", False, str(exc))

    # every invalid fixture is rejected
    for f in invalids:
        check(f"invalid rejected: {f}", rejects(_load(f)))

    check("fixture counts (3 valid, 7 invalid)", len(valids) == 3 and len(invalids) == 7,
          f"got {len(valids)} valid / {len(invalids)} invalid")

    # --- per-tooth mutation: start from a valid edge and make each guard fire on its own ---
    base_inst = _load("institutional-promoted.valid.json")
    base_cs = _load("commonsense-defeasible.valid.json")

    # CE-T1: commonsense must be defeasible
    m = copy.deepcopy(base_cs); m["spec"]["defeasible"] = False; m["spec"]["status"] = "promoted"
    check("CE-T1 commonsense-must-be-defeasible fires", rejects(m))

    # CE-T2: institutional must be authoritative (defeasible=false)
    m = copy.deepcopy(base_inst); m["spec"]["defeasible"] = True
    check("CE-T2 institutional-must-be-authoritative fires", rejects(m))

    # CE-T3: institutional/schema require provenance.source
    m = copy.deepcopy(base_inst); m["spec"].pop("provenance", None)
    check("CE-T3 provenance-complete fires", rejects(m))

    # CE-T4: truth in [0,1]
    m = copy.deepcopy(base_cs); m["spec"]["truth"]["confidence"] = 1.2
    check("CE-T4 truth-in-range fires", rejects(m))
    m = copy.deepcopy(base_cs); m["spec"]["truth"]["strength"] = True  # bool is not a number
    check("CE-T4 truth-bool-rejected fires", rejects(m))

    # CE-T5: valid interval well-formed
    m = copy.deepcopy(base_inst)
    m["spec"]["temporal"] = {"validFromMicros": 10, "validToMicros": 5}
    check("CE-T5 valid-interval fires", rejects(m))

    # CE-T6: authority requires promotion
    m = copy.deepcopy(base_inst); m["spec"]["status"] = "candidate"
    check("CE-T6 authority-requires-promotion fires", rejects(m))

    # CE-T7: no transaction clock on the edge
    m = copy.deepcopy(base_cs)
    m["spec"].setdefault("temporal", {})["txn_created"] = 1
    check("CE-T7 no-txn-clock-on-edge fires", rejects(m))

    # negative-of-negative: the base valids still pass after we stop mutating (guards aren't over-biting)
    check("base institutional still valid", not rejects(_load("institutional-promoted.valid.json")))
    check("base commonsense still valid", not rejects(_load("commonsense-defeasible.valid.json")))

    print(f"\n{_passed} passed, {_failed} failed")
    return 1 if _failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
