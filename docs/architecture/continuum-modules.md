# Open Agent Continuum — component map

- **Owner:** @mdheller
- **Status:** active
- **Last reviewed:** 2026-08-03
- **Version:** 0.1
- **Related ADRs:** [ADR-0001](../adr/ADR-0001-open-agent-continuum.md), [ADR-0002](../adr/ADR-0002-governed-cognition-functor.md)

The owning page for every continuum runtime module. Each module lives under `tools/<module>/` with its own
README + conformance suite; this page is the single index so no runtime object is undocumented.

| Module (`tools/…`) | WO | Role | Verify |
|---|---|---|---|
| `cypher-atomspace-gateway` | WO-A | Cypher-subset façade over the canonical graph (HellGraph); dual-enforced hop/LIMIT caps; `Graph.QueryCypher` triRPC verb | `python3 tests/conformance_test.py` |
| `proof-artifact-spine` | WO-B | Knowledge `publish=f_!` → hash-chained, tamper-evident, replayable ProofArtifact; fail-closed AC-1 | `python3 tests/wo_b_test.py` |
| `workspace-controller` | WO-C | Workspace epistemic ceiling (meet over mounts; external ≤ Derived) + mount-diff → `authorityChange` → review | `python3 tests/wo_c_test.py` |
| `sherlock-scout` | WO-D | Grounded/ungrounded RAG answer card, ceiling-clamped, receipted; never fabricates grounding | `python3 tests/wo_d_test.py` |
| `sherlock-shell` | WO-E | Matrix room controller — room powers projected from the mount table; receipted provisioning | `python3 tests/wo_e_test.py` |
| `agent-term` | WO-F | Command palette (`Alias.Resolve`) + computer-use controller: never the host, disposable-VM-only, Sentinel-gated, evidence-bearing | `python3 tests/wo_f_test.py` |
| `fibration-node` | WO-H | Semantic-Fibration node model: S¹/S²/S³, descent (glue/degrade/block), FIB-9 decay, truth-survives-the-loop | `python3 tests/wo_h_test.py` |
| `metadata-intake` | MS-P2 | Canonical metadata-record at intake (hash-first BLAKE3+SHA-256, three-time, classification), validated + Intake CustodyEvent | `python3 tests/wo_msp2_test.py` |
| `zone-lifecycle` | MS-P5 | WNZL Dirt-to-Diamond zone lifecycle: one owning zone, gated promotion, demotion, retirement-not-destruction | `python3 tests/wo_msp5_test.py` |
| `artifact-registry` | MS-P6 | evidence_grade E1–E5 ⟷ epistemic-ceiling ladder + AC-01..12 artifact-class registry with per-class enrichment/zone routing | `python3 tests/wo_msp6_test.py` |
| `image-promotion-gate` | WO-G | SourceOS image validation gate — EvidenceBundle IS a ProofArtifact; fail-closed promotion + PolicyException | `python3 tests/wo_g_test.py` |
| `analysis-views` | AV-1 | Registered governed LSA/LDA/LSI analysis-view descriptor (reproducibility seed+hashes) fused with WNZL zone_path + epistemic ceiling + provenance | `python3 tests/av1_test.py` |
| `cskg-edge` | WO-A+ | Governance-bearing CSKG edge for the gateway: epistemic tier + defeasibility (commonsense is never authoritative), edge-level provenance, valid/observation-time typing (no transaction clock on the edge) | `python3 tools/cskg-edge/tests/cskg_edge_test.py` |
| `temporal-retrieval-filter` | GAP-2 | Uniform temporal-correctness contract: schema-agnostic `TemporalRetrievalFilter` (`FieldMap` decouples any surface's field names) — suppress superseded, most-recent (max `valid_from`) wins; consumes regis#20's invariant (oracle-pinned), applies across RAG router / memory-mesh / search. ADR-0002 §8 GAP-2 (#84) | `python3 tools/temporal-retrieval-filter/tests/conformance_test.py` |
| `knowledge-engineering` | KE-1 | Knowledge/Dictionary-Engineering workbench (Watson-Knowledge-Studio equivalent). `KnowledgeEngineeringWorkspace` binds documentSet → annotations (regis semantic-role #22/#27) → entity/relation types (REFERENCE regis entity-class #16 / semantic-role-kind #22 / ontogenesis OWL/SHACL) → dictionaries that BIND governed **Systema Concept Entries** (ontogenesis Platform/Systema) → rules → versions → modelRef. Teeth (KE-T1..T9): static-match dictionary REJECTED (learn-don't-match); type/rule not in a governed registry REJECTED; promotion without a receipt REJECTED; human override (add/overwrite/annotate/define) with no author/receipt REJECTED; supersession retains the prior version; every promotion + authorship event receipted on the `proof-artifact-spine` | `python3 tools/knowledge-engineering/tests/ke_test.py` |
| `agent-cognition-er` | ER-1 | Typed entity/relation contract for governed cognition (ADR-0002 data-model companion): 17 entities + 18 relations, each bound to its owning estate mechanism (`mechanism_ref`); auditable-by-construction teeth (every ACTION `gated_by` POLICY_CHECK + `recorded_as` AUDIT_EVENT; every PROVENANCE_RECORD `depends_on` DATASET_VERSION + `includes` MODEL_VERSION; every memory item carries topic_set+span+domain). Memory-type ↔ ER binding reconciling memory-mesh#47 FSMS with the Claude memory pattern. | `python3 tools/agent-cognition-er/tests/conformance_test.py` |
| `labor-request-contract` | WO-B | Request-centric labor contract (Labor Network Charter #108): `labor = request → response → evidence → fulfillment → trust`, each stage a hash-chained `ProofArtifact` on the `proof-artifact-spine` (ADR-0001). Shape + chain teeth: an out-of-order stage, a missing-evidence fulfillment, or a broken receipt chain is REJECTED. | `python3 tools/validate_labor_contract.py` |
| `graphrag-grounding` | KH-1 | GraphRAG grounded-answer-with-page-reference contract (Knowledge Hub #76): grades a grounded answer against retrieval-page-accuracy + QA-F1 floors, seals every answer (VERIFY or REJECTED) on the `proof-artifact-spine`, and emits Annotation/Document/Tag nodes + ANNOTATES/TAGGED edges. Teeth: below-accuracy-floor / low-QA-F1 / no-page-refs / unresolvable-ref REJECTED and still receipted; REJECTED answers clamped to Speculative; tampered ledger fails verification. | `python3 tools/graphrag-grounding/tests/grounding_test.py` |

## Data flow

```
question
  → workspace-controller  (S¹ mount + S² ceiling; reachability)
  → query-router  (logical + semantic route; graph→vector fallback; RouteDecision on the spine — WO-A2)
  → text-to-sql / self-query  (query construction: NL→safe parameterised SELECT + NL→Qdrant metadata filter — WO-A3)
  → cypher-atomspace-gateway  (intent-routed 1–2 hop retrieval, safe subset)
  → temporal-retrieval-filter  (temporal correctness: suppress superseded, most-recent-fact wins — GAP-2)
  → sherlock-scout  (answer card: answer/evidence/citations/freshness/confidence/missing-info/next-actions)
  → grounded-assistant  (tech-support product surface: 5 grounded bots over the scout card; every answer evidence-backed + receipted — WO-D)
  → proof-artifact-spine  (hash-chained, replayable ProofArtifact — AC-1)
operated via sherlock-shell (Matrix rooms) and agent-term (CLI); reflexively governed by fibration-node
(descent + decay; truth = what survives the loop).
```

The receipt spine's **inference arm** is live in production (receipt-gateway, prophet-platform
#1233/#1237). Runtime bindings for the rest (live HellGraph, Agent-S guest runner, live Synapse, shared
`Ledger.Push`) are tracked under epic #33.

## Adding a `tools/<module>`

Adding a new `tools/<module>/` (any directory with a `README.md`)? **Name it here in the same PR** — add a
row to the table above and, where it fits, a line in the `## Data flow` block. The `docs-lint` CI gate
(`tools/validate_docs.py` coverage check) fails closed until every module is named on this page, so no
runtime object ships undocumented. This convention exists because PRs #77, #89, and #97 each added a module
and hit the gate after the fact (prophet-workspace#76). Run it locally before you push:

```sh
python3 tools/validate_docs.py            # coverage + metadata + link drift; exit 1 = fix before pushing
python3 tools/tests/validate_docs_test.py # the gate's own self-test (teeth)
```
