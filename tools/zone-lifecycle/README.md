# zone-lifecycle (MS-P5) — WNZL Dirt-to-Diamond

The zone lifecycle over the workspace controller (Metadata Standards §5). Every artifact has exactly
**one owning zone**; promotion up the ordered path is **gated** (fail-closed); demotion is permitted;
**destruction is forbidden** — the only terminal is Retirement (hash preserved). Every transition emits a
CustodyEvent (MS-P4) onto the FIPS-approved receipt spine.

```
Discovery(0) → Landing(1) → Examination(2) → Integration(3) → Governed(4) → Diamond(5)
```

## Gates (per transition)
- **Discovery→Landing** — complete intake re-processing.
- **Landing→Examination** — intake CustodyEvent + hashes computed + identity block complete.
- **Examination→Integration** — evidence_grade ≥ E3 + counter_explanations + classification complete.
- **Integration→Governed** — analyst sign-off (+ legal review if required).
- **Governed→Diamond** — signed ForensicBundle + disclosure authorization + recipient identified.

## API
- `promote(state, …)` — one zone up if the gate passes → **ZonePromotion** event; a failed gate emits a **PolicyException** and raises (fail-closed).
- `demote(state, to_zone, …)` — to a lower zone → **ZoneDemotion** event.
- `retire(state, …)` — the only terminal → **Retirement** event; hash preserved. **No destroy/delete API exists.**

## Verify
`python3 tests/wo_msp5_test.py` → **13/13** — full gated path, unmet-gate refusal + PolicyException, demotion, retirement-not-destruction, one-owning-zone, custody chain verifies.
