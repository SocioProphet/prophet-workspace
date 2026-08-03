# cskg-edge — governance-bearing CSKG edge (Kairos/Chronos deck follow-on)

The **edge-level contract** the WO-A `cypher-atomspace-gateway` can consume. The gateway today carries
only a bare `TruthValue{strength,confidence}` per CSKG edge (`tools/cypher-atomspace-gateway/adapter.py`).
This module upgrades the edge to carry the governance the Masonmark **"Schema-Grounded KAIROS/CHRONOS
CSKG"** deck demands, distilled from the one queued unit
`~/dev/spec-intake/2026-08-03/Masonmark_Updated_2026_SchemaGrounded_KairosChronos_CSKG.pptx` (slides
53–54, *Ontology Grounding + Commonsense Priors*).

## The one idea the deck actually adds

The deck's slides 53–55 are DARPA-KAIROS-style **schema-grounded event reasoning**, not a two-clock time
model. Its sharpest, most buildable rule is on slide 54: **CSKG/ConceptNet commonsense is *defeasible
support*, never institutional truth.** The estate already owns the pieces this needs — the E1–E5 authority
ladder (`artifact-registry`), the epistemic ceiling (`fibration-node`), provenance + the **three-time
model** (`metadata-intake` `temporal`: `txn_created` / `valid_*` / `observed_at`) — but they live on the
*artifact/record*, not on the *graph edge*. This schema **projects them onto the edge** so the gateway can
refuse to let a commonsense prior authorize a result.

This is why the deck's "Kairos/Chronos" framing needs **no new clock**: event-time vs system-time is
already the estate three-time model. The edge therefore carries **valid-time + observation-time only**;
transaction/system-time stays on the record/ledger (CE-T7).

## What's here (spec-as-code)

| Path | Role |
|---|---|
| `schemas/cskg-edge.schema.json` | The edge descriptor — public-CSKG-compatible (`node1`/`relation`/`node2` + lifted cols) plus `truth · epistemicTier · defeasible · status · provenance · temporal` (JSON Schema draft 2020-12; authority laws as `if/then` guards). |
| `validate_cskg_edge.py` | Dependency-light validator (no `jsonschema`): the cross-field teeth pure schema can't express, plus a `validate_schema` drift-guard so schema and code can't diverge. |
| `examples/*.valid.json` / `*.invalid.json` | 3 conforming edges (institutional / commonsense / schema) + one negative fixture per tooth. |
| `tests/cskg_edge_test.py` | Conformance both ways + a targeted mutation that makes each guard fire individually (stdlib, no pytest). |

## The teeth (enforced both ways)

- **CE-T1 commonsense is defeasible** — `epistemicTier=commonsense` ⇒ `defeasible=true`. A commonsense
  edge can never be authoritative (deck slide 54; the core rule).
- **CE-T2 institutional is authoritative** — `epistemicTier=institutional` ⇒ `defeasible=false`.
- **CE-T3 provenance-complete** — `institutional`/`schema` tiers require `provenance.source` (bind to a
  governed id/source, not a raw string).
- **CE-T4 truth in range** — `strength`, `confidence` ∈ [0,1] (bool rejected).
- **CE-T5 valid-interval well-formed** — `validFromMicros ≤ validToMicros` (validator-only; the one
  cross-field rule pure JSON Schema cannot state).
- **CE-T6 authority requires promotion** — a non-defeasible edge must be `status=promoted`; a `candidate`
  (cairnmark) or `tombstoned` edge cannot authorize.
- **CE-T7 no transaction clock on the edge** — `temporal` accepts valid-time + observation-time only; a
  `txn_created`/system clock is rejected (it belongs to the record/ledger three-time model).

## Verify

```
python3 tools/cskg-edge/validate_cskg_edge.py     # validates examples/; asserts *.invalid.json reject
python3 tools/cskg-edge/tests/cskg_edge_test.py   # conformance both ways + per-tooth mutation
```

## Runtime follow-up (tracked with the gap issue)

This is the **contract**; wiring is the runtime half. The gateway's `expand()` composes `TruthValue`
along a path — binding this schema means (a) tagging each hit with its `epistemicTier`/`defeasible`,
(b) refusing to let a `defeasible` hit authorize a result on its own, and (c) carrying `provenance` +
valid-time through the answer card into the `proof-artifact-spine`. Tracked under epic #33 alongside the
gap analysis.
