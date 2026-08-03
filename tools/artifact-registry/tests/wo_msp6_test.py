"""MS-P6 conformance — `python3 tools/artifact-registry/tests/wo_msp6_test.py` (no pytest).

Teeth: the evidence_grade⟷epistemic-ceiling map is correct + monotonic + round-trips at the floor; the
AC-01..12 registry has all 12 classes with valid, in-order WNZL zone paths; enrichment/zone routing works
and unknown classes/grades are rejected; the class names match the metadata-record schema enum.
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
sys.path.insert(0, PKG)

import grade_ladder as GL  # noqa: E402
import artifact_registry as AR  # noqa: E402

_passed = _failed = 0


def check(name, cond, detail=""):
    global _passed, _failed
    if cond:
        _passed += 1; print(f"  ok   {name}")
    else:
        _failed += 1; print(f"  FAIL {name} :: {detail}")


def main() -> int:
    # --- grade ladder ---
    check("E1..E5 map to expected levels",
          [GL.grade_to_level(g) for g in GL.EVIDENCE_GRADES] == ["Speculative", "Derived", "Derived", "Measured", "Proved"])
    check("map is monotonic (order-preserving)", GL.is_monotonic())
    check("ladder self-consistency (floors round-trip, targets in WO-C LEVELS)", GL.check_consistency() == [], str(GL.check_consistency()))
    check("floor grades", GL.level_floor_grade("Proved") == "E5" and GL.level_floor_grade("Measured") == "E4"
          and GL.level_floor_grade("Derived") == "E2" and GL.level_floor_grade("Speculative") == "E1")
    check("E5 meets a Proved ceiling; E4 does not", GL.grade_meets_ceiling("E5", "Proved") and not GL.grade_meets_ceiling("E4", "Proved"))
    check("E4 meets a Measured ceiling; E3 does not", GL.grade_meets_ceiling("E4", "Measured") and not GL.grade_meets_ceiling("E3", "Measured"))
    check("E1 meets only Speculative", GL.grade_meets_ceiling("E1", "Speculative") and not GL.grade_meets_ceiling("E1", "Derived"))
    try:
        GL.grade_to_level("E9"); check("unknown grade rejected", False)
    except GL.LadderError:
        check("unknown grade rejected", True)

    # --- artifact registry ---
    check("registry has all 12 classes (AC-01..12)", len(AR.REGISTRY) == 12 and set(AR.REGISTRY) == {f"AC-{i:02d}" for i in range(1, 13)})
    check("registry validates (complete + valid WNZL zone paths)", AR.validate_registry() == [], str(AR.validate_registry()))
    check("by_id + by_name agree", AR.by_id("AC-02")["name"] == "ConsolePaste" and AR.by_name("ConsolePaste") is AR.by_id("AC-02"))
    check("enrichment routing", "panic-save detection" in AR.enrichment_path("ConsolePaste"))
    check("zone routing (LegalFiling reaches Governed)", "Governed" in AR.zone_path("LegalFiling"))
    check("FirmwareDump stops at Examination (specialist)", AR.zone_path("FirmwareDump") == ["Landing", "Examination"])
    try:
        AR.by_name("Hologram"); check("unknown class rejected", False)
    except AR.RegistryError:
        check("unknown class rejected", True)

    # --- cross-check: class names match the metadata-record schema enum + grades are E1..E5 ---
    import json
    schema_path = os.path.join(PKG, "..", "metadata-intake", "schemas", "metadata-record.schema.json")
    if os.path.exists(schema_path):
        schema = json.load(open(schema_path))
        enum = set(schema["$defs"]["artifactClass"]["enum"]) - {"Other"}
        reg_names = {e["name"] for e in AR.REGISTRY.values()}
        check("registry class names match the metadata-record schema enum", enum == reg_names, str(enum ^ reg_names))
        grade_enum = set(schema["properties"]["classification"]["properties"]["evidence_grade"]["enum"])
        check("evidence grades match the schema enum", grade_enum == set(GL.EVIDENCE_GRADES))
    else:
        print("  (skip schema cross-check — vendored schema not present in this tree)")

    print(f"\n{_passed} passed, {_failed} failed")
    return 1 if _failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
