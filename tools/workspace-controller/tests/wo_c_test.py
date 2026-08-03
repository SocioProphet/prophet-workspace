"""WO-C conformance — `python3 tests/wo_c_test.py` (no pytest dep).

Consumes the REAL mount table from #39 (examples/workspace-mount-table.example.json) and verifies the
epistemic gap WO-C adds on top of it:
  - workspace ceiling = meet over mounts, clamped to Derived for external principals (STAR-1);
  - a publish above the ceiling is denied;
  - mount-table diffs map to authorityChange + Layer (widening = Layer 2 review; narrowing = Layer 1).
"""
from __future__ import annotations

import copy
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
REPO = os.path.dirname(os.path.dirname(PKG))   # tools/workspace-controller -> repo root
sys.path.insert(0, PKG)

from epistemic_ceiling import (  # noqa: E402
    CeilingError, admit_publish, authority_change, workspace_ceiling,
)

_passed = _failed = 0


def check(name, cond, detail=""):
    global _passed, _failed
    if cond:
        _passed += 1; print(f"  ok   {name}")
    else:
        _failed += 1; print(f"  FAIL {name} :: {detail}")


def load_example() -> dict:
    with open(os.path.join(REPO, "examples", "workspace-mount-table.example.json")) as f:
        return json.load(f)


def main() -> int:
    table = load_example()
    src_a = table["spec"]["entries"][0]["sourceId"]
    src_b = table["spec"]["entries"][1]["sourceId"]

    # --- ceiling: all-default (Derived) meet ---
    c_int = workspace_ceiling(table, external=False)
    check("internal ceiling = Derived (default meet)", c_int.level == "Derived", c_int.level)

    # a Measured + Proved mount internally -> meet is the min (Measured)
    c_hi = workspace_ceiling(table, external=False,
                             source_levels={src_a: "Measured", src_b: "Proved"})
    check("meet is the MIN over mounts", c_hi.level == "Measured" and c_hi.meet == "Measured", f"{c_hi}")

    # a Speculative mount drags the whole workspace down
    c_lo = workspace_ceiling(table, external=False, source_levels={src_a: "Speculative"})
    check("one Speculative mount -> Speculative ceiling", c_lo.level == "Speculative", c_lo.level)

    # external principal is clamped to Derived even with high mounts (STAR-1)
    c_ext = workspace_ceiling(table, external=True,
                              source_levels={src_a: "Measured", src_b: "Proved"})
    check("external clamped to Derived (STAR-1)",
          c_ext.level == "Derived" and c_ext.clamped_by_external and c_ext.meet == "Measured", f"{c_ext}")

    # --- admit_publish against the ceiling ---
    admit_publish(c_int, "Derived")   # ok, no raise
    check("publish at ceiling permitted", True)
    try:
        admit_publish(c_int, "Measured")
        check("publish above ceiling denied", False, "Measured allowed at Derived ceiling")
    except CeilingError as e:
        check("publish above ceiling denied", e.code == "above-ceiling", e.code)

    # --- authority_change diffs ---
    same = authority_change(table, table)
    check("no change -> none / Layer 1", same.change == "none" and same.layer == 1 and not same.review_required)

    # add a mount -> expanded / Layer 2 / review
    widened = copy.deepcopy(table)
    widened["spec"]["entries"].append({
        "sourceId": "workspace-source:mail/inbox", "surface": "mail",
        "capabilities": ["read"], "grantedBy": "authority://sociosphere/grants",
        "grantRef": "grant://x"})
    aw = authority_change(table, widened)
    check("added mount -> expanded / Layer 2 / review",
          aw.change == "expanded" and aw.layer == 2 and aw.review_required and "workspace-source:mail/inbox" in aw.added,
          f"{aw}")

    # remove a mount -> reduced / Layer 1
    ar = authority_change(widened, table)
    check("removed mount -> reduced / Layer 1", ar.change == "reduced" and ar.layer == 1 and not ar.review_required, f"{ar}")

    # widen a capability on a retained source -> expanded / Layer 2
    capwide = copy.deepcopy(table)
    capwide["spec"]["entries"][1]["capabilities"] = ["read", "subscribe"]
    ac = authority_change(table, capwide)
    check("added capability -> expanded / Layer 2", ac.change == "expanded" and ac.layer == 2, f"{ac}")

    # wider extent -> expanded
    wider_ext = copy.deepcopy(table)
    base_ext = table["spec"]["declaredExtent"]
    wider_ext["spec"]["declaredExtent"] = base_ext + "/subteam"
    ae = authority_change(table, wider_ext)
    check("wider extent -> expanded / Layer 2", ae.change == "expanded" and ae.layer == 2, f"{ae}")

    # incomparable extent -> ambiguous / Layer 2 (fail-safe to review)
    incomp = copy.deepcopy(table)
    incomp["spec"]["declaredExtent"] = "extent://unrelated/thing"
    ai = authority_change(table, incomp)
    check("incomparable extent -> ambiguous / Layer 2", ai.change == "ambiguous" and ai.layer == 2, f"{ai}")

    print(f"\n{_passed} passed, {_failed} failed")
    return 1 if _failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
