"""publish = f_! — the gated, receipted aggregation from a workspace into the estate (WO-B).

The adjunction's costly arrow (ADR-0001 §3): mount (f*) is free; publish (f_!) is gated + settled +
**receipted**. This module is the reference publish path:

    gate (extent/phase + cover disjointness + inclusion-exclusion on overlaps)
      -> emit ProofArtifact into the hash-chained ledger   [MUST succeed]
      -> return the receipt

AC-1 (the receipt law): a publish that cannot emit a receipt is NOT a publish. The gate is fail-closed —
if ledger emission raises, publish raises and nothing is considered published.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from proof_artifact import ProofArtifactError, RunPackage, canonical, emit_proof_artifact

# Epistemic ceiling for external principals (STAR-1). A publish above this from an external agent is denied.
_LEVELS = {"Speculative": 0, "Derived": 1, "Measured": 2, "Proved": 3}
EXTERNAL_CEILING = "Derived"


class PublishDenied(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


@dataclass
class PublishRequest:
    agent: str
    external: bool               # external principals are capped at EXTERNAL_CEILING (STAR-1)
    extent: str
    phase: str
    epistemic_level: str
    inputs: str                  # canonical text of what is being published (hashed into the receipt)
    run: RunPackage
    cover: list[str] = field(default_factory=list)          # section ids this publish writes
    existing_covers: list[list[str]] = field(default_factory=list)  # already-published overlapping covers


def _inclusion_exclusion(cover: list[str], existing: list[list[str]]) -> dict:
    """On overlapping covers, record which sections are NEW vs already-covered so the estate does not
    double-count an aggregation (SP-ARCH-004 WS-3). Returns the inclusion record stamped on the receipt."""
    already = set()
    for c in existing:
        already |= set(c)
    new = [s for s in cover if s not in already]
    overlap = [s for s in cover if s in already]
    return {"cover": list(cover), "new_sections": new, "overlap_sections": overlap,
            "net_added": len(new)}


def publish(req: PublishRequest, ledger: Path) -> dict:
    """Execute f_!: gate -> emit receipt (fail-closed) -> return receipt. Raises PublishDenied /
    ProofArtifactError; on either, nothing is published."""
    # 1) epistemic ceiling for external principals (STAR-1 / AC-2)
    if req.external:
        if _LEVELS.get(req.epistemic_level, 99) > _LEVELS[EXTERNAL_CEILING]:
            raise PublishDenied(
                "epistemic-ceiling",
                f"external principal cannot publish at {req.epistemic_level} (ceiling {EXTERNAL_CEILING})")
    if req.epistemic_level not in _LEVELS:
        raise PublishDenied("epistemic-unknown", f"unknown epistemic level {req.epistemic_level!r}")

    # 2) basic gate: extent + phase must be declared (FIB-1: no publish without a declared extent)
    if not req.extent or not req.phase:
        raise PublishDenied("extent-undeclared", "publish requires a declared extent and phase")

    # 3) inclusion-exclusion on overlapping covers
    incl = _inclusion_exclusion(req.cover, req.existing_covers)

    # 4) emit the receipt — fail-closed. If this raises, the publish fails (AC-1).
    try:
        receipt = emit_proof_artifact(
            ledger, extent=req.extent, phase=req.phase, epistemic_level=req.epistemic_level,
            agent=req.agent, inputs=req.inputs, run=req.run, inclusion_record=incl)
    except ProofArtifactError as e:
        raise PublishDenied("receipt-required", f"publish refused — no receipt could be emitted ({e})") from e

    return receipt


def replay(receipt: dict) -> dict:
    """Reconstruct the run from its ProofArtifact and re-verify the output hash — the auditor path
    ('load a package, show plan -> tool_calls -> outputs -> policy'). Raises if the package was tampered."""
    from proof_artifact import sha256
    run = receipt["runPackage"]
    if sha256(canonical(run)) != receipt["outputHash"]:
        raise PublishDenied("replay-mismatch", "run package does not match the receipt outputHash")
    return {"plan": run["plan"], "tool_calls": run["tool_calls"],
            "outputs": run["outputs"], "policy_report": run["policy_report"],
            "verified": True, "seq": receipt["ledgerSeq"]}
