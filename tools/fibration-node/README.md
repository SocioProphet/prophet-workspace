# fibration-node (WO-H) — the per-node topology of knowing

Makes the Semantic-Fibration worldview operational for each intelligent mesh node. WO-H of
[ADR-0001](../../docs/adr/ADR-0001-open-agent-continuum.md).

- **S³** = the shared hypergraph (HellGraph) · **S¹** = the node's fiber (its mounted cover, WO-C) ·
  **S²** = the node's projected worldview (what it holds, at what epistemic level).

## What it computes

- **descent per section** — does the node's LOCAL view glue with the SHARED (S³) view?
  `glues` → full · `degraded` → read-only at `Speculative`, the disagreement **localised in place** (WS-6)
  · `blocked` → gate closed here and above (non-localisable, the conflict spans the cover).
- **project_worldview** — S² = meet over sections, clamped to `Derived` for external nodes (STAR-1);
  gated if any section is blocked; obstructions surfaced, never hidden.
- **FIB-9 decay** — a section stale by ≥1 window drops a level; ≥2 windows forces read-only.
- **fiber_alignment** — ontology (model) vs epistemology (observed): converge → resonance, diverge →
  misaligned fiber (a descent obstruction at the fiber level).
- **survives_loop** — *truth is what survives the loop*: a claim is true iff its section **glues** after
  descent + decay **and** carries a valid ProofArtifact (WO-B). Degraded / blocked / unreceipted claims
  do not survive.

Levels reuse WO-C (`Speculative < Derived < Measured < Proved`) — one vocabulary across the continuum.

## Verify

`python3 tests/wo_h_test.py` → **19/19**: glue/degrade/block descent, obstruction-in-place, decay steps +
read-only threshold, S² meet + gating + external clamp, alignment resonance/misalignment, and the
survives-the-loop truth condition.

## Runtime follow-up (tracked #45)

Bind S³ to the live HellGraph (#34) so descent runs against real shared sections; feed decay windows from
the FIB-9 refresh cadence; surface obstructions in the Sherlock Shell room UI (WO-E) as degraded-in-place.
