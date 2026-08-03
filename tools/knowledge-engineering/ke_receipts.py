#!/usr/bin/env python3
"""KE receipt binding — CONSUMES the proof-artifact-spine (WO-B) to receipt KE promotions + authorship.

The Knowledge-Engineering workbench does not invent a receipt spine. Every promotion (annotation -> type /
dictionary entry) and every human authorship event (add/overwrite/annotate/define) is a knowledge publish
(f_!) and is sealed on the SAME hash-chained, tamper-evident ProofArtifact ledger the rest of the estate
uses (SHA-256 = FIPS-180-4 algorithm). This module is the thin adapter: it builds the RunPackage for a KE
event and returns the `sha256:` receipt id that the KEWorkspace record references (ReceiptRef, KE-T8).

Runtime follow-up: route these through the shared `Ledger.Push` triRPC verb (ADR-0001, epic #33), and for
Systema-side promotions mint the parallel knowledge-state-lifecycle `urn:srcos:receipt:*` id.
"""
from __future__ import annotations

import sys
from pathlib import Path

# consume the estate receipt spine (WO-B), do not fork it
_SPINE = Path(__file__).resolve().parents[1] / "proof-artifact-spine"
sys.path.insert(0, str(_SPINE))

import proof_artifact as PA  # noqa: E402


def receipt_promotion(ledger: Path, *, annotation_id: str, target_kind: str, ref: str,
                      agent: str = "ke-workbench@0.1.0", epistemic_level: str = "Derived") -> dict:
    """Receipt an annotation -> type/dictionary-term promotion. Returns the ProofArtifact (entryHash is the
    KEWorkspace promotionReceiptRef)."""
    run = PA.RunPackage(
        plan=[f"promote annotation {annotation_id} -> {target_kind} {ref}"],
        tool_calls=[{"tool": "ke.promote", "annotationId": annotation_id, "targetKind": target_kind, "ref": ref}],
        outputs=[{"kind": target_kind, "ref": ref}],
        policy_report={"gate": "governed-registry + source-anchor", "verdict": "admit"},
    )
    return PA.emit_proof_artifact(ledger, extent="knowledge-engineering", phase="promote",
                                  epistemic_level=epistemic_level, agent=agent,
                                  inputs=f"{annotation_id}->{ref}", run=run)


def receipt_authorship(ledger: Path, *, event_id: str, op: str, target_ref: str, author: str,
                       version: int, supersedes: str | None,
                       agent: str = "ke-workbench@0.1.0") -> dict:
    """Receipt a human authorship event (add/overwrite/annotate/define). The user is a first-class author;
    an overwrite supersedes the prior version (retained). Returns the ProofArtifact."""
    run = PA.RunPackage(
        plan=[f"{op} {target_ref} by {author} (v{version}" + (f", supersedes {supersedes}" if supersedes else "") + ")"],
        tool_calls=[{"tool": "ke.author", "op": op, "target": target_ref, "author": author,
                     "version": version, "supersedes": supersedes}],
        outputs=[{"targetRef": target_ref, "version": version, "supersedes": supersedes}],
        policy_report={"gate": "author-attributed + versioned + supersession", "verdict": "admit"},
    )
    return PA.emit_proof_artifact(ledger, extent="knowledge-engineering", phase=f"author:{op}",
                                  epistemic_level="Derived", agent=agent,
                                  inputs=f"{event_id}:{op}:{target_ref}:v{version}", run=run)
