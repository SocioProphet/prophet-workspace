# Program gaps, open obligations & work-order register

- **Owner:** @mdheller
- **Status:** active
- **Last reviewed:** 2026-08-03
- **Related:** [ADR-0001](adr/ADR-0001-open-agent-continuum.md)

This is the single register for the Open Agent Continuum program. It answers "any gaps you need — respond here" from the source specs, and sequences the work orders. Each WO is (or becomes) a tracked GitHub issue.

## A. Gaps I need answered (blocking or shaping)

| # | Gap | Why it matters | Proposed default (used unless you say otherwise) |
|---|---|---|---|
| G1 | **Homeserver identity** — which Matrix homeserver domain(s) back Sherlock Shell (`:server` in aliases)? | Room aliases are a stability contract for OS help features. | Placeholder `<server>` in docs until confirmed; no hard-coded domain. |
| G2 | **Canonical AtomSpace runtime** — is there an existing AtomSpace service in the estate, or do we stand one up (hyperon/opencog)? | WO-A's adapter binds to it; "AtomSpace canonical, Neo4j mirror-only". | Assume we stand up a hyperon AtomSpace service behind triRPC; Neo4j optional validation only. |
| G3 | **triRPC ↔ receipt spine binding** — does the estate's triRPC/TriuneRPC already define `Ledger.Push`? | AC-1 requires every publish to receipt; reuse not reinvent. | Reuse the existing receipt-gateway + ledger; add `Ledger.Push` as a thin verb over it. |
| G4 | **LampStand ↔ Sherlock boundary** — lampstand is the local desktop indexer; Sherlock Search federates above it. Confirm the handoff contract (already sketched in `SHERLOCK_SEARCH_ROLE.md`). | Avoids Sherlock re-implementing local indexing. | Sherlock consumes lampstand via `Search.Text`; no duplication. |
| G5 | **agent-term provenance** — Agent-S runs Python to control the computer. Which VM/attestation profile is the controller container allowed? | Safety: it must be controller-of-disposable-VMs, never resident-privileged. | Controller container + disposable guest VMs only; host actions Sentinel-gated. |
| G6 | **Sherlock repos** — `sherlock-search`, `sherlock-cases`, `sherlock-shell` — which exist vs. to-create? | Determines whether WOs are "extend" or "bootstrap". | Verify per SP-ARCH-004 §12.1 before each WO leaves Proposed. |

## B. Open obligations (verify before a WO leaves Proposed)

Carried from ADR-0001 §9 and the source specs:
1. prophet-workspace must actually distinguish `publish` from `save` + have a mount-authority check (SP-ARCH-004 §12.1).
2. AtomSpace canonical vs Neo4j mirror — a test must fail if Neo4j is treated as authority.
3. Relation-normalization map is an API — version it, test migrations (same fork class as Noetica #602).
4. receipt-gateway SPOF/chokepoint before it fronts publish traffic (prophet-platform #1238).
5. Cypher cost model mandatory before `WHERE`/joins land.
6. Descent-as-DoS mitigation (minimum-cover-fraction) is partial.
7. Superconscious falsification harness unrun.

## C. Work orders (sequenced; thin slice = WO-A → WO-B → WO-D)

| WO | Title | Depends on | Acceptance |
|---|---|---|---|
| **WO-A** | Cypher→AtomSpace gateway (safe subset + conformance tests + Sentinel hop/LIMIT caps) | — | rejects unbounded query at gateway *and* Sentinel; 1–2 hop expand returns rows+edges+TruthValue; conformance suite green |
| **WO-B** | Receipt spine: `publish`=`f_!` emits ProofArtifact/Quilt run package (extends receipt-gateway + ledger) | WO-A | a publish with no receipt fails a test; run package replays (plan→tool_calls→outputs→policy→ledger) |
| **WO-C** | Workspace controller slice: mount table + epistemic ceiling (SP-ARCH-004 WO-22/23) | — | external principal capped at `Derived`, cannot widen own mount table; mount table renders as a diff |
| **WO-D** | Sherlock Scout v0: grounded RAG answer card in Matrix, receipted | WO-A, WO-B, WO-C | one real question answered in a triage room with citations + freshness + confidence + a replayable ProofArtifact |
| **WO-E** | Sherlock Shell: Matrix room admin automation (per `docs/ops` runbook) | WO-D | case room created via checklist; bot powers derive from a mount table; approvals receipted |
| **WO-F** | agent-term CLI: Agent-S controller + triRPC verbs (`Alias.Resolve`, `Graph.QueryCypher`) | WO-C | controller-container + disposable-VM only; host actions Sentinel-gated; runs a scenario, emits evidence |
| **WO-G** | SourceOS image validation gates (EvidenceBundle = ProofArtifact); agent-term shipped in image | WO-F | no Git update/task-close without passing promotion gate; evidence bundle complete + replay ref |
| **WO-H** | Semantic-Fibration node model: S¹ mount / S² projection / descent alignment per mesh node | WO-A | ontology↔epistemology divergence surfaces as a descent obstruction (WS-6), not hidden |
| **WO-I** | Documentation Enrichment: complete Phase-1 stubs + Phase-4 drift control (lint/coverage/link-check) | WO-D | every runtime object in ADR-0001 has an owning page; docs-lint runs in CI |

## D. Status

- **Foundation (this PR):** ADR-0001, the docs-as-code tree, the Matrix room-admin runbook (v0.2), and this register. Spec-as-code, not yet runtime.
- **Receipt spine (shipped):** receipt-gateway fronts embeddings for memoryd/hellgraph/health-twin/sherlock-engine (prophet-platform #1233, #1237). This is WO-B's inference arm, already live — WO-B extends it to knowledge `publish`.
- **Next:** WO-A (Cypher→AtomSpace gateway) — the substrate façade the whole loop reads through.
