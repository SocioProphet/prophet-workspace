"""ER-1 conformance — `python3 tools/agent-cognition-er/tests/conformance_test.py` (no pytest dep).

Teeth both ways, with per-tooth mutation of a known-good instance:
  - a fully-formed governed-cognition instance VERIFIES (auditable-by-construction);
  - an ACTION with no POLICY_CHECK is REJECTED (T3a);
  - an ACTION with no AUDIT_EVENT is REJECTED (T3b);
  - a memory item with no topic_set / span / domain is REJECTED (T2);
  - a PROVENANCE_RECORD missing DATASET_VERSION is REJECTED (T4a);
  - a PROVENANCE_RECORD missing MODEL_VERSION is REJECTED (T4b);
  - an undeclared relation edge is REJECTED (T5);
  - an untyped POLICY_CHECK (empty reason_code) is REJECTED (T1/T6);
  - the memory-type ↔ ER binding drift guard holds, and make_memory_item enforces the scope envelope.
"""
from __future__ import annotations

import copy
import json
import os
import sys
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
sys.path.insert(0, PKG)

from agent_cognition_er import (  # noqa: E402
    ENTITIES, RELATIONS, MEMORY_SCOPED, ERError, required_edges, tally, validate_er_instance,
)
from memory_binding import (  # noqa: E402
    MEMORY_BINDINGS, MEMORY_BINDINGS_BY_TYPE, MemoryBindingError,
    make_memory_item, validate_memory_binding,
)

_passed = _failed = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global _passed, _failed
    if cond:
        _passed += 1; print(f"  ok   {name}")
    else:
        _failed += 1; print(f"  FAIL {name} :: {detail}")


def rejects(name: str, instance: dict) -> None:
    try:
        validate_er_instance(instance)
    except ERError:
        check(name, True)
        return
    check(name, False, "expected ERError (REJECTED) but instance was ACCEPTED")


def good_instance() -> dict:
    return json.loads((Path(PKG) / "examples/full-cycle.valid.json").read_text(encoding="utf-8"))


def main() -> int:
    # --- structural ---
    check("17 entities", len(ENTITIES) == 17, str(len(ENTITIES)))
    check("18 relations", len(RELATIONS) == 18, str(len(RELATIONS)))
    check("4 required edges (the teeth)", len(required_edges()) == 4,
          str([f"{r.subject}-{r.predicate}->{r.object}" for r in required_edges()]))
    check("5 memory-scoped entities", len(MEMORY_SCOPED) == 5, str(MEMORY_SCOPED))
    t = tally()
    check("tally sums to 17 entities", sum(t["entities"].values()) == 17, str(t["entities"]))
    check("tally sums to 18 relations", sum(t["relations"].values()) == 18, str(t["relations"]))

    # --- the happy path VERIFIES ---
    try:
        validate_er_instance(good_instance())
        check("full governed-cognition instance VERIFIES", True)
    except ERError as exc:
        check("full governed-cognition instance VERIFIES", False, str(exc))

    # --- T3a: ACTION with no POLICY_CHECK is REJECTED ---
    inst = good_instance()
    inst["edges"] = [e for e in inst["edges"] if not (e[0] == "act:001" and e[1] == "gated_by")]
    rejects("T3a ACTION with no POLICY_CHECK -> REJECTED", inst)

    # --- T3b: ACTION with no AUDIT_EVENT is REJECTED ---
    inst = good_instance()
    inst["edges"] = [e for e in inst["edges"] if not (e[0] == "act:001" and e[1] == "recorded_as")]
    rejects("T3b ACTION with no AUDIT_EVENT -> REJECTED", inst)

    # --- T2: memory item with no topic_set/span/domain is REJECTED (each field) ---
    for field in ("topic_set", "span", "domain"):
        inst = good_instance()
        del inst["entities"]["OBSERVATION"][0][field]
        rejects(f"T2 memory item missing {field} -> REJECTED", inst)

    # --- T4a / T4b: PROVENANCE_RECORD missing dataset/model edge is REJECTED ---
    inst = good_instance()
    inst["edges"] = [e for e in inst["edges"] if not (e[0] == "prov:001" and e[1] == "depends_on")]
    rejects("T4a PROVENANCE_RECORD missing DATASET_VERSION -> REJECTED", inst)

    inst = good_instance()
    inst["edges"] = [e for e in inst["edges"] if not (e[0] == "prov:001" and e[1] == "includes")]
    rejects("T4b PROVENANCE_RECORD missing MODEL_VERSION -> REJECTED", inst)

    # --- T5: undeclared relation edge is REJECTED ---
    inst = good_instance()
    inst["edges"].append(["act:001", "runs", "cycle:001"])   # ACTION-runs-DECISION_CYCLE not declared
    rejects("T5 undeclared relation edge -> REJECTED", inst)

    # --- T1/T6: untyped POLICY_CHECK (empty reason_code) is REJECTED ---
    inst = good_instance()
    inst["entities"]["POLICY_CHECK"][0]["reason_code"] = ""
    rejects("T6 untyped POLICY_CHECK (empty reason_code) -> REJECTED", inst)

    # --- memory binding ---
    try:
        validate_memory_binding()
        check("memory-binding drift guard holds", True)
    except MemoryBindingError as exc:
        check("memory-binding drift guard holds", False, str(exc))

    check("6 memory types bound", len(MEMORY_BINDINGS) == 6, str(len(MEMORY_BINDINGS)))
    check("episodic -> OBSERVATION+AUDIT_EVENT",
          MEMORY_BINDINGS_BY_TYPE["episodic"].er_nodes == ("OBSERVATION", "AUDIT_EVENT"))
    check("working -> BELIEF_STATE",
          MEMORY_BINDINGS_BY_TYPE["working"].er_nodes == ("BELIEF_STATE",))
    check("procedural -> PLAN",
          MEMORY_BINDINGS_BY_TYPE["procedural"].er_nodes == ("PLAN",))
    check("semantic -> GRAPH_ENTITY+FAIR_METADATA",
          MEMORY_BINDINGS_BY_TYPE["semantic"].er_nodes == ("GRAPH_ENTITY", "FAIR_METADATA"))

    # make_memory_item enforces the scope envelope
    item = make_memory_item("OBSERVATION", topic_set=["t"], span={"valid_from": "x"}, domain="d",
                            observation_id="o", cycle_id="c")
    check("make_memory_item builds a scoped item",
          item["topic_set"] == ["t"] and item["domain"] == "d" and "span" in item)
    try:
        make_memory_item("OBSERVATION", topic_set=[], span={"valid_from": "x"}, domain="d")
        check("make_memory_item rejects empty topic_set", False, "no error raised")
    except MemoryBindingError:
        check("make_memory_item rejects empty topic_set", True)

    print(f"\n{_passed} passed, {_failed} failed")
    return 1 if _failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
