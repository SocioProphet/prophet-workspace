"""WO-D conformance — the thin vertical slice end to end. `python3 tests/wo_d_test.py` (no pytest).

Proves the continuum: a Sherlock Scout question -> WO-C ceiling + mount gate -> WO-A retrieval ->
answer card -> WO-B receipted ProofArtifact that replays. Teeth both ways: grounded answers cite
evidence and are receipted; ungrounded answers hedge (no fabricated grounding) and are STILL receipted;
external principals are clamped to Derived; a Speculative-ceiling workspace clamps even a grounded answer.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
TOOLS = os.path.dirname(PKG)
sys.path.insert(0, PKG)
sys.path.insert(0, os.path.join(TOOLS, "cypher-atomspace-gateway"))
sys.path.insert(0, os.path.join(TOOLS, "proof-artifact-spine"))

from adapter import InMemoryFixtureAdapter  # noqa: E402
from proof_artifact import verify_ledger      # noqa: E402
from publish import replay                     # noqa: E402
from scout import answer                       # noqa: E402

_passed = _failed = 0


def check(name, cond, detail=""):
    global _passed, _failed
    if cond:
        _passed += 1; print(f"  ok   {name}")
    else:
        _failed += 1; print(f"  FAIL {name} :: {detail}")


def graph() -> InMemoryFixtureAdapter:
    a = InMemoryFixtureAdapter()
    a.load_cskg([
        {"head": "baxter", "relation": "Causes", "tail": "flood", "strength": 0.9, "confidence": 0.8},
        {"head": "flood", "relation": "Causes", "tail": "damage", "strength": 0.8, "confidence": 0.7},
        {"head": "baxter", "relation": "IsA", "tail": "facility", "strength": 0.95, "confidence": 0.9},
    ])
    return a


def mount_table(caps=("read", "reference"), source="workspace-source:docs/baxter-brief") -> dict:
    return {"apiVersion": "workspace.socioprophet.dev/v1", "kind": "WorkspaceMountTable",
            "metadata": {"tableId": "workspace-mount-table:test", "createdAt": "2026-08-03T00:00:00Z"},
            "spec": {"workspaceId": "workspace://test", "declaredExtent": "extent://cases/p1",
                     "entries": [{"sourceId": source, "surface": "docs", "capabilities": list(caps),
                                  "grantedBy": "authority://sociosphere/grants", "grantRef": "grant://x"}],
                     "policyRef": "policy://test", "evidenceCorrelationId": "ec://test"}}


def main() -> int:
    q_grounded = "What caused the Baxter facility shutdown?"
    q_off = "What is the capital of France?"

    with tempfile.TemporaryDirectory() as d:
        # 1) grounded answer, internal principal
        led = Path(d) / "l1.jsonl"
        r = answer(q_grounded, mount_table=mount_table(), graph_adapter=graph(), ledger=led, external=False)
        card, rec = r["card"], r["receipt"]
        check("grounded: card is grounded", card.grounded, card.answer)
        check("grounded: cites evidence", len(card.citations) >= 1 and card.confidence > 0, f"{card.citations}")
        check("grounded: answer names the cause (flood)", "flood" in card.answer, card.answer)
        check("grounded: receipted at seq 0", rec["ledgerSeq"] == 0 and rec["recordType"] == "ProofArtifact")
        ok, msg = verify_ledger(led); check("grounded: ledger verifies", ok, msg)
        rp = replay(rec); check("grounded: run package replays", rp["verified"])
        check("grounded: epistemic level Derived", card.epistemic_level == "Derived", card.epistemic_level)

        # 2) ungrounded answer — hedge, no fabricated grounding, STILL receipted
        led2 = Path(d) / "l2.jsonl"
        r2 = answer(q_off, mount_table=mount_table(), graph_adapter=graph(), ledger=led2, external=False)
        c2 = r2["card"]
        check("ungrounded: not grounded", not c2.grounded)
        check("ungrounded: no fabricated citations", c2.citations == [] and c2.confidence == 0.0)
        check("ungrounded: missing-info set", bool(c2.missing_info))
        check("ungrounded: STILL receipted (answer contract)", r2["receipt"]["ledgerSeq"] == 0)
        check("ungrounded: level Speculative", c2.epistemic_level == "Speculative")

        # 3) nothing readable mounted -> ungrounded "no source mounted"
        led3 = Path(d) / "l3.jsonl"
        r3 = answer(q_grounded, mount_table=mount_table(caps=("subscribe",)), graph_adapter=graph(),
                    ledger=led3, external=False)
        check("no readable mount -> ungrounded", not r3["card"].grounded)
        check("no readable mount -> reason names it", "mounted" in (r3["card"].missing_info or ""),
              r3["card"].missing_info)

        # 4) external principal clamped to Derived even with a Measured source
        led4 = Path(d) / "l4.jsonl"
        src = "workspace-source:docs/baxter-brief"
        r4 = answer(q_grounded, mount_table=mount_table(), graph_adapter=graph(), ledger=led4,
                    external=True, source_levels={src: "Measured"})
        check("external: grounded answer clamped to Derived", r4["card"].epistemic_level == "Derived",
              r4["card"].epistemic_level)
        check("external: receipt records Derived", r4["receipt"]["epistemicLevel"] == "Derived")

        # 5) Speculative-ceiling workspace clamps even a grounded answer to Speculative
        led5 = Path(d) / "l5.jsonl"
        r5 = answer(q_grounded, mount_table=mount_table(), graph_adapter=graph(), ledger=led5,
                    external=False, source_levels={src: "Speculative"})
        check("Speculative ceiling clamps grounded answer", r5["card"].grounded and r5["card"].epistemic_level == "Speculative",
              f"grounded={r5['card'].grounded} level={r5['card'].epistemic_level}")

    print(f"\n{_passed} passed, {_failed} failed")
    return 1 if _failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
