"""WO-F conformance — `python3 tests/wo_f_test.py` (no pytest).

Teeth: aliases resolve to triRPC verbs (unknown rejected); the computer-use controller REFUSES a host
target, runs only in a disposable VM, is Sentinel-gated (offline-first blocks networked actions), and
receipts every action with its evidence; dispatch composes WO-A (Graph.QueryCypher) and the controller.
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
from aliases import AliasError, registry, resolve  # noqa: E402
from controller import ComputerUseController, ControllerDenied, Sentinel, VmResult  # noqa: E402
from cli import dispatch                        # noqa: E402

_passed = _failed = 0


def check(name, cond, detail=""):
    global _passed, _failed
    if cond:
        _passed += 1; print(f"  ok   {name}")
    else:
        _failed += 1; print(f"  FAIL {name} :: {detail}")


class FixtureVm:
    """A stand-in disposable-VM executor. Never touches the host — returns synthetic evidence."""
    def __init__(self):
        self.ran = []

    def run_in_disposable_vm(self, command: str) -> VmResult:
        self.ran.append(command)
        return VmResult(stdout=f"[vm] {command}", action_trace=[{"step": "exec", "cmd": command}],
                        evidence_refs=[f"screenshot://vm/{len(self.ran)}"])


def graph():
    a = InMemoryFixtureAdapter()
    a.load_cskg([{"head": "rain", "relation": "IsA", "tail": "weather", "strength": 0.9, "confidence": 0.9}])
    return a


def main() -> int:
    # --- alias resolution ---
    rv = resolve("g rain")
    check("g -> Graph.QueryCypher (read)", rv.verb == "Graph.QueryCypher" and rv.action_class == "read")
    check("g passes lemma param", rv.params["params"]["lemma"] == "rain")
    rv2 = resolve("g rain IsA")
    check("g with relation filter", rv2.params["params"].get("rel") == "IsA")
    rv3 = resolve("vm ls -la")
    check("vm -> ComputerUse.Run (compute-use)", rv3.verb == "ComputerUse.Run" and rv3.action_class == "compute-use")
    try:
        resolve("frobnicate x")
        check("unknown alias rejected", False, "resolved unknown alias")
    except AliasError as e:
        check("unknown alias rejected", e.code == "unknown-alias", e.code)
    try:
        resolve("g")
        check("missing args rejected", False)
    except AliasError as e:
        check("missing args rejected", e.code == "args-missing", e.code)
    check("registry is introspectable", "g" in registry() and registry()["vm"]["action_class"] == "compute-use")

    with tempfile.TemporaryDirectory() as d:
        led = Path(d) / "at.jsonl"
        vm = FixtureVm()
        ctl = ComputerUseController(vm, led)

        # --- controller safety ---
        try:
            ctl.run("rm -rf /", target="host")
            check("host target REFUSED before execution", False, "host action ran")
        except ControllerDenied as e:
            check("host target REFUSED before execution", e.code == "host-forbidden", e.code)
        check("nothing executed on refusal", vm.ran == [])

        # disposable-vm action runs + receipts + carries evidence
        out = ctl.run("echo hi")
        check("disposable-vm action runs", vm.ran == ["echo hi"] and "hi" in out["result"].stdout)
        rec = out["receipt"]
        check("compute-use receipted (seq 0)", rec["ledgerSeq"] == 0 and rec["recordType"] == "ProofArtifact")
        check("receipt carries evidence refs",
              rec["runPackage"]["outputs"][0]["evidence_refs"] == ["screenshot://vm/1"], str(rec["runPackage"]["outputs"][0]))
        ok, msg = verify_ledger(led); check("controller ledger verifies", ok, msg)
        check("compute-use run replays", replay(rec)["verified"])

        # Sentinel offline-first blocks a networked action
        try:
            ctl.run("curl http://evil.example/x")
            check("offline-first blocks networked action", False, "networked action ran")
        except ControllerDenied as e:
            check("offline-first blocks networked action", e.code == "offline-first", e.code)

        # networked allowed when offline_first disabled (explicit exception)
        ctl_net = ComputerUseController(FixtureVm(), Path(d) / "net.jsonl", Sentinel(offline_first=False))
        on = ctl_net.run("curl https://ok.example")
        check("networked allowed when policy opts in", "ok.example" in on["result"].stdout)

        # --- dispatch composes WO-A + controller ---
        dg = dispatch("g rain", graph_adapter=graph())
        check("dispatch g -> gateway rows", dg["verb"] == "Graph.QueryCypher" and any(r.get("t.form") == "weather" for r in dg["rows"]))
        dv = dispatch("vm echo composed", controller=ComputerUseController(FixtureVm(), Path(d) / "d2.jsonl"))
        check("dispatch vm -> controller + receipt", dv["verb"] == "ComputerUse.Run" and dv["receipt"]["ledgerSeq"] == 0)

    print(f"\n{_passed} passed, {_failed} failed")
    return 1 if _failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
