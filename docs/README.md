# Sherlock / Open Agent Continuum — Documentation (docs-as-code)

- **Owner:** @mdheller
- **Status:** active
- **Last reviewed:** 2026-08-03
- **Version:** 0.2

This tree makes the Sherlock agent plane **operationally legible** — good enough for operators to run it, engineers to extend it, auditors to inspect it, evaluators to measure it, and support staff to trust it. Docs live beside the code and every runtime object has an owning page.

Start here: **[ADR-0001 — The Open Agent Continuum](adr/ADR-0001-open-agent-continuum.md)** (the architecture-of-record unifying Sherlock, the SP-ARCH-004 workspace controller, and the receipt spine), **[ADR-0002 — Governed Cognition as an Emergent Functor](adr/ADR-0002-governed-cognition-functor.md)** (the estate-wide 5-layer / 13-step conformance audit that generalises ADR-0001), and **[Program gaps & open obligations](PROGRAM_GAPS_AND_OPEN_OBLIGATIONS.md)** (the sequenced work orders).

## Structure

| Dir | Contents |
|---|---|
| `adr/` | Architecture decisions. Every non-trivial decision gets one. |
| `architecture/` | Product vision, context/container/component/data-flow diagrams, threat model, trust-boundary map, failure-mode analysis, compatibility matrix. |
| `ops/` | Homeserver/room/bridge/webhook admin, IAM, encryption posture, backup/restore, incident response, capacity planning, observability. |
| `search/` | Ingestion pipeline, parser matrix, chunking/embedding/reranking/citation policy, collection model, ACL propagation, freshness/recrawl, lineage. |
| `agents/` | Tool contract catalog, action-approval policy, planner constraints, error taxonomy, retry semantics, handoff/escalation criteria, case/actor/world/self-state schemas. |
| `cases/` | Case state machine, room-class runbooks, case lifecycle. |
| `evals/` | Benchmark inventory, seed inventories, golden-support set, retrieval/answer/tool-call/routing eval specs, cost/latency budgets, model-comparison scorecards. |
| `security/` | Trust boundaries, encryption, key management, data handling, redaction. |
| `product/` | Product vision, user journeys, acceptance matrices. |
| `reference/` | Provider universe (per model/provider: prompting/eval/tool-use/RAG guidance, pricing, quotas, governance notes, our eval strengths/weaknesses), glossary. |

## Minimum metadata for every page

Every doc page starts with: `owner`, `status` (draft/active/deprecated), `last reviewed`, `version`, and the relevant `related services / ADRs / dashboards / runbooks`.

## Enrichment phases

1. **Skeletal coverage** — a stub for every required page with owner, outline, and unanswered questions. *(this PR seeds `adr/`, `ops/`, and the tree; remaining stubs tracked as WO-I.)*
2. **Operational hardening** — fill runbooks first (room admin ✅ started; case admin, connector failures, index rebuild, degraded-mode, bridge cutover).
3. **Evidence & screenshots** — state diagrams, API examples, room examples, redacted incident transcripts.
4. **Drift control** — nightly docs lint, coverage report, link checker, schema/doc consistency, dashboard-link + runbook-review checks.

## Anti-patterns (enforced in Phase 4)

Undocumented bot powers · undocumented room aliases · undocumented corpus sources · screenshots without a text source of truth · benchmarks without grading rules · prompt templates without owners · dashboards without action thresholds.
