"""Computer-use controller for agent-term (WO-F of ADR-0001).

Agent-S runs Python to control a computer — so the safety contract is structural, not advisory:

  1. NEVER the host. Computer-use actions run ONLY in a DISPOSABLE guest VM. A host/resident target is
     refused before anything executes. The controller has no code path that touches the host.
  2. Sentinel-gated. Offline-first by policy: a networked action is blocked unless explicitly enabled.
  3. Every action emits evidence. Each run produces a ProofArtifact (WO-B) carrying the action trace +
     evidence refs (screenshots / OCR / replay), so a computer-use action is auditable and replayable.

The disposable-VM executor is a Protocol with a fixture implementation for conformance; the real Agent-S
guest runner is a drop-in (runtime follow-up, WO-G ships it in the image).
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

for _p in ("proof-artifact-spine",):
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), _p))

from proof_artifact import RunPackage       # noqa: E402  (WO-B)
from publish import PublishRequest, publish  # noqa: E402  (WO-B)


class ControllerDenied(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


@dataclass
class VmResult:
    stdout: str
    action_trace: list = field(default_factory=list)   # e.g. [{"step":"click","x":..}, ...]
    evidence_refs: list = field(default_factory=list)   # screenshot/OCR/replay pointers


class DisposableVmExecutor(Protocol):
    """Runs a command in a fresh, throwaway guest VM. Implementations MUST NOT touch the host."""
    def run_in_disposable_vm(self, command: str) -> VmResult: ...


@dataclass
class Sentinel:
    offline_first: bool = True
    max_command_len: int = 4000
    _NETWORK_TOKENS = ("curl ", "wget ", "http://", "https://", "ssh ", "scp ", "nc ")

    def check(self, command: str) -> None:
        if len(command) > self.max_command_len:
            raise ControllerDenied("command-too-long", "command exceeds Sentinel length cap")
        if self.offline_first and any(tok in command for tok in self._NETWORK_TOKENS):
            raise ControllerDenied("offline-first", "networked action blocked by offline-first policy")


class ComputerUseController:
    def __init__(self, executor: DisposableVmExecutor, ledger: Path, sentinel: Sentinel | None = None,
                 *, extent: str = "extent://agent-term", external: bool = False):
        self.executor = executor
        self.ledger = Path(ledger)
        self.sentinel = sentinel or Sentinel()
        self.extent = extent
        self.external = external

    def run(self, command: str, *, target: str = "disposable-vm") -> dict:
        """Run a computer-use command in a disposable VM, Sentinel-gated, and receipt it. Raises
        ControllerDenied on a host target or a policy block — before any execution."""
        # 1) NEVER the host — structural refusal (rule 1)
        if target != "disposable-vm":
            raise ControllerDenied(
                "host-forbidden",
                f"computer-use target {target!r} refused — agent-term acts only in a disposable VM")
        # 2) Sentinel policy (rule 2)
        self.sentinel.check(command)
        # 3) execute in the throwaway guest
        res = self.executor.run_in_disposable_vm(command)
        # 4) evidence-bearing receipt (rule 3)
        receipt = publish(
            PublishRequest(
                agent="agent-term", external=self.external, extent=self.extent, phase="compute-use",
                epistemic_level="Derived", inputs=command,
                run=RunPackage(
                    plan=[f"target=disposable-vm offline_first={self.sentinel.offline_first}"],
                    tool_calls=[{"tool": "ComputerUse.Run", "command": command, "target": target}],
                    outputs=[{"stdout": res.stdout, "action_trace": res.action_trace,
                              "evidence_refs": res.evidence_refs}],
                    policy_report={"offline_first": self.sentinel.offline_first, "target": "disposable-vm"}),
                cover=[]),
            self.ledger)
        return {"result": res, "receipt": receipt}
