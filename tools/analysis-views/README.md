# analysis-views (AV-1) — LSA/LSI/LDA as registered governed analysis views

AV-1 of [issue #60](../../docs/adr/ADR-0001-open-agent-continuum.md). Makes the GENESYS three-space model
(LSA/LSI/LDA) real in the estate as **Noria-style materialized analysis views** that are **registered and
governed** — not a second, ungoverned embedding plane, and not the 23×6 governance intent grid (that is
routing; this is corpus analytics).

Each view is one descriptor that fuses the two halves the estate otherwise keeps apart:

- **GENESYS Ring-Zero reproducibility** — pinned `seed`, `output_hash` / `manifest_hash`, deterministic
  reconstruction (closed-space builders; LSA dim 512 / LSI rank 256 / LDA k 64 are the spec defaults).
- **Estate governance** — WNZL `zone_path` (MS-P5 zone-lifecycle), epistemic `access` ceiling (WO-C),
  and `provenance` (WO-B). A view is owned by exactly one WNZL zone and reachable only up to its ceiling.

## What's here (spec-as-code)

| Path | Role |
|---|---|
| `schemas/analysis-view.schema.json` | The registered-view descriptor: **identity · model · source · transform · integrity · lifecycle · governance** (JSON Schema draft 2020-12). |
| `validate_analysis_view.py` | Validator: JSON Schema **+** the cross-field "teeth" pure schema can't express. Self-checking negative fixtures. |
| `examples/*.valid.json` / `*.invalid.json` | Conforming descriptors (LSA / LSI-governed-expansion / LDA) + one negative fixture per tooth. |
| `tests/av1_test.py` | Conformance both ways + a targeted mutation that makes each guard fire individually. |

## The teeth (cross-field rules, enforced both ways)

- **AV-T1 model↔params** — LSA needs `dim` only; LSI needs `rank` only; LDA needs `k` only. Carrying
  another model's basis param is a silent fork risk → reject.
- **AV-T2 reproducibility** — an `output_hash` requires a pinned deterministic reconstruction
  (`reconstruction.deterministic && from_seed`). A hash you cannot regenerate is not evidence.
- **AV-T3 WNZL order** — `zone_path` must be strictly ascending in `Discovery→…→Diamond` (MS-P5).
- **AV-T4 governed publication** — a view owning `Governed`/`Diamond` requires `signed` + `manifest_hash`
  + `provenance.signer` (mirrors the zone-lifecycle Governed/Diamond gates).
- **AV-T5 external clamp** — `origin=external` caps `epistemic_ceiling` at `Derived` (AC-2 / STAR-1).
- **AV-T6 emergence gate** — a `transform.expansion` (rank bump / topic split-merge) requires
  `coverage.ratio == 1.0` **and** a `stability` block: GENESYS "fully fibered before expansion".
- **AV-T7 lifecycle coherence** — eviction ≠ `none` needs a freshness window; deterministic
  reconstruction needs non-empty `source_refs` (cannot reconstruct from nothing).

## Verify

```
pip install jsonschema
python3 tools/analysis-views/validate_analysis_view.py   # validates examples/; asserts *.invalid.json reject
python3 tools/analysis-views/tests/av1_test.py           # conformance both ways + per-tooth mutation
```

## Provenance & follow-up

Distilled from the GENESYS Three-Space (Ring-Zero) + Ring-1 fiber/projection unit
(`~/dev/spec-intake/2026-08-03/`). The Ring-1 continuous-geometry worldview (fiber bundle, connection,
holonomy, octonion boundary) is the **same** worldview already made operational by **WO-H
`tools/fibration-node`** in discrete, governance-grade form — consumed, not forked. AV-1 is the one
genuinely-new buildable piece: the three semantic spaces as governed, reproducible, registered views.
Runtime follow-up (tracked with the gap issue): bind the descriptor to real Noria-style incremental
maintenance and emit a CustodyEvent on each refresh/expansion so the view's lifecycle is replayable.
