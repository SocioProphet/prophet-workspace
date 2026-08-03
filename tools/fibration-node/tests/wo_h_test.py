"""WO-H conformance — `python3 tests/wo_h_test.py` (no pytest).

Teeth: a section that agrees with S3 glues (full); a localisable disagreement degrades read-only with the
conflict SURFACED IN PLACE (never hidden); a disagreement that spans the cover is blocked (gate closed);
FIB-9 decay lowers the level and eventually forces read-only; the S2 projection meets over sections and
clamps external nodes; ontology<->epistemology divergence is a misaligned fiber; and only glued, receipted
claims survive the loop.
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
sys.path.insert(0, PKG)

from node_model import (  # noqa: E402
    Section, descend_section, fiber_alignment, project_worldview, survives_loop,
)

_passed = _failed = 0


def check(name, cond, detail=""):
    global _passed, _failed
    if cond:
        _passed += 1; print(f"  ok   {name}")
    else:
        _failed += 1; print(f"  FAIL {name} :: {detail}")


def main() -> int:
    # --- glues ---
    g = Section(id="s1", local_value="flooding", shared_value="flooding", declared_level="Derived")
    vg = descend_section(g, {"s1": g})
    check("agreement -> glues / full / Derived", vg.verdict == "glues" and vg.mode == "full" and vg.level == "Derived")
    check("glued + receipted survives the loop", survives_loop(vg, has_proof_artifact=True))
    check("glued but UN-receipted does NOT survive", not survives_loop(vg, has_proof_artifact=True and False))

    # --- localisable disagreement -> degraded, surfaced in place ---
    d = Section(id="s2", local_value="sabotage", shared_value="flooding", declared_level="Derived",
                overlaps=["s3"])
    ok_overlap = Section(id="s3", local_value="q", shared_value="q")  # overlap glues -> localisable
    vd = descend_section(d, {"s2": d, "s3": ok_overlap})
    check("localisable disagreement -> degraded / read-only / Speculative",
          vd.verdict == "degraded" and vd.mode == "read-only" and vd.level == "Speculative")
    check("disagreement surfaced IN PLACE (not hidden)",
          vd.obstruction and vd.obstruction["local"] == "sabotage" and vd.obstruction["shared"] == "flooding")
    check("degraded claim does NOT survive the loop", not survives_loop(vd, has_proof_artifact=True))

    # --- non-localisable -> blocked (overlap also disagrees) ---
    b = Section(id="s4", local_value="x", shared_value="y", declared_level="Measured", overlaps=["s5"])
    bad_overlap = Section(id="s5", local_value="p", shared_value="q")  # overlap ALSO disagrees
    vb = descend_section(b, {"s4": b, "s5": bad_overlap})
    check("non-localisable disagreement -> blocked", vb.verdict == "blocked" and vb.mode == "blocked")
    check("blocked names the conflicting overlaps", vb.obstruction["conflicting_overlaps"] == ["s5"])
    check("blocked claim does NOT survive", not survives_loop(vb, has_proof_artifact=True))

    # --- FIB-9 decay ---
    stale1 = Section(id="s6", local_value="v", shared_value="v", declared_level="Proved", windows_since_refresh=1.0)
    v1 = descend_section(stale1, {"s6": stale1})
    check("1 window stale -> level drops (Proved->Measured), still glues", v1.verdict == "glues" and v1.level == "Measured", v1.level)
    stale2 = Section(id="s7", local_value="v", shared_value="v", declared_level="Proved", windows_since_refresh=2.0)
    v2 = descend_section(stale2, {"s7": stale2})
    check("2 windows stale -> read-only (FIB-9 degrade)", v2.mode == "read-only" and v2.level == "Derived", f"{v2.mode}/{v2.level}")

    # --- S2 projection: meet + gating + external clamp ---
    p = project_worldview([g, d], external=False)   # g glues Derived, d degraded Speculative
    check("S2 ceiling = meet over sections (Speculative)", p.s2_ceiling == "Speculative", p.s2_ceiling)
    check("S2 surfaces obstructions", len(p.obstructions) == 1)
    check("S2 not gated without a blocked section", not p.gated)

    p2 = project_worldview([g, b, bad_overlap], external=False)  # b blocked
    check("S2 gated when a section is blocked", p2.gated)

    hi = Section(id="s8", local_value="v", shared_value="v", declared_level="Proved")
    p_ext = project_worldview([hi], external=True)
    check("external node clamped to Derived (STAR-1)", p_ext.s2_ceiling == "Derived", p_ext.s2_ceiling)
    p_int = project_worldview([hi], external=False)
    check("internal node keeps Proved", p_int.s2_ceiling == "Proved", p_int.s2_ceiling)

    # --- fiber alignment (ontology vs epistemology) ---
    res = fiber_alignment({"rain": "weather", "flood": "damage"}, {"rain": "weather", "flood": "damage"})
    check("convergence -> resonance", res["aligned"] and res["state"] == "resonance")
    mis = fiber_alignment({"rain": "weather"}, {"rain": "clear-sky"})
    check("divergence -> misaligned fiber", not mis["aligned"] and mis["divergences"] == ["rain"])

    print(f"\n{_passed} passed, {_failed} failed")
    return 1 if _failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
