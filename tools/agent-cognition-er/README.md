# agent-cognition-er (ER-1)

The **entity/relation contract for governed agent cognition** — the data-model companion to
[ADR-0002 — Governed Cognition as an Emergent Functor](../../docs/adr/ADR-0002-governed-cognition-functor.md).
ADR-0002 audits the cognition *loop* (5 layers, 13 steps); this module makes the cognition *entity/relation
model* — "auditable & reproducible **by construction**" — a typed, validatable contract, and binds every
entity to the estate mechanism that already owns it (`mechanism_ref`). Consume-not-fork: no new store.

The reference ER's tokens originate in the estate's unified cognitive systems map
(`prophet-platform/apps/socioprophet-web/public/workbench/unified_cognitive_systems_map.html`).

## The law it enforces (why "by construction")

`validate_er_instance()` makes the illegal states unrepresentable in a *valid* instance, so an auditor
reads structure, not prose. The **teeth**:

- **T2** — every memory item (`OBSERVATION`, `GRAPH_ENTITY`, `VECTOR_CHUNK`, `BELIEF_STATE`, `PLAN`) carries
  `topic_set` + `span` + `domain`, or it is **REJECTED**. Memory is scoped, never ambient.
- **T3** — every `ACTION` is `gated_by` a `POLICY_CHECK` **and** `recorded_as` an `AUDIT_EVENT`, or it is
  **REJECTED**. This is ADR-0002's AC-1/AC-2 on the graph: no action without lawful promotion, no promotion
  without a receipt.
- **T4** — every `PROVENANCE_RECORD` `depends_on` a `DATASET_VERSION` **and** `includes` a `MODEL_VERSION`, or
  it is **REJECTED**. A receipt that cannot name its data + model is not replayable.
- **T5** — every edge is a **declared** relation (typed subject/predicate/object); **T1/T6** — every record
  carries its key fields and every gating `POLICY_CHECK` is a typed decision (`outcome` + `reason_code`).

## Pieces

| File | Role |
|---|---|
| `agent_cognition_er.py` | Schema-as-code: the 17 entities + 18 relations as typed, verdicted, mechanism-bound models; `validate_er_instance()` (the teeth); `tally()`. |
| `memory_binding.py` | Memory-type ↔ ER binding: the 6 FSMS memory types (memory-mesh#47) + Claude pattern onto ER nodes, the auto-dream ↔ promotion/forgetting map, and `make_memory_item()` (enforces the `topic_set`/`span`/`domain` envelope). |
| `schemas/agent-cognition-er.schema.json` | JSON Schema for an ER instance (enum lists **drift-guarded** against the Python model). |
| `validate_agent_cognition_er.py` | Runs the model check + memory-binding drift guard + schema-drift guard + every fixture both ways. Fail-closed. |
| `conformance_matrix.md` | HAVE/PARTIAL/GAP per entity + relation (grounded in files) + the memory binding + the GAPs. |
| `examples/*.valid.json` / `*.invalid.json` | Fixtures: one full auditable instance + one per tooth that must be REJECTED. |
| `tests/conformance_test.py` | Teeth both ways with per-tooth mutation. Run below. |

## Verify

```
python3 tools/agent-cognition-er/validate_agent_cognition_er.py
python3 tools/agent-cognition-er/tests/conformance_test.py     # 24/24
```

## Tally

35 rows → **28 HAVE · 7 PARTIAL · 0 GAP**. PARTIALs + live wiring filed as GAP-ER-1..5 (see
`conformance_matrix.md`). Cross-refs: ADR-0002, memory-mesh#47, ontogenesis#140, prophet-workspace#76/#108,
policy-fabric#102.
