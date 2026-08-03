# workspace-controller — epistemic ceiling + mount-authority change (WO-C)

The **epistemic dimension** over the mount table. The mount (`f*`) capability surface already exists
(A4-31 / #39: `schemas/workspace-mount-table.schema.json`, WS-5 no-self-grant enforced). WO-C adds only
what that schema lacks, **consuming** it — never rewriting it. WO-C of
[ADR-0001](../../docs/adr/ADR-0001-open-agent-continuum.md).

## What it adds

- **`workspace_ceiling()`** — the workspace epistemic level = the **meet (min)** over its mounted
  sections' levels, then **clamped to `Derived` for an external principal** (STAR-1 / AC-2). This is the
  S²-projection ceiling of ADR-0001 §4; levels match the ProofArtifact spine (WO-B): `Speculative <
  Derived < Measured < Proved`.
- **`admit_publish()`** — a publish/answer may not exceed the workspace ceiling.
- **`authority_change()`** — diffs two mount tables into `WorkspaceInterfaceCrossing.authorityChange`
  (`none | reduced | expanded | ambiguous`) and the **Layer**: widening (`expanded`/`ambiguous`) is
  **Layer 2 → review required** (WS-5); narrowing/none is **Layer 1 → free**. This is the order relation
  in B, wired to the existing `interface-crossing` review path rather than a new primitive.

## Bindings (verified against real artifacts)

- reads `examples/workspace-mount-table.example.json` (#39) directly in the conformance suite;
- `authority_change` output feeds `contracts/workspace/interface-crossing.schema.json` (`authorityChange`
  + `review`);
- epistemic levels align with WO-B (`proof-artifact-spine`) so a publish's claimed level, the workspace
  ceiling, and the receipted level are one vocabulary.

## Verify

`python3 tests/wo_c_test.py` → **12/12** (meet, external clamp, above-ceiling denial, and the full
authority-change matrix: none/reduced/expanded/ambiguous incl. capability-widening and extent order).

## Follow-up (tracked)

Per-entry epistemic classification currently comes from a `source_levels` map (source catalog); once the
source catalog exposes classifications, wire it in. A schema note to add an optional `epistemicLevel` to
mount-table entries is worth coordinating with the A4-31 owner (kept out of this PR to avoid touching #39's
`additionalProperties:false` schema).
