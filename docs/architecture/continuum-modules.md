# Open Agent Continuum — component map

- **Owner:** @mdheller
- **Status:** active
- **Last reviewed:** 2026-08-03
- **Version:** 0.1
- **Related ADRs:** [ADR-0001](../adr/ADR-0001-open-agent-continuum.md)

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

## Data flow

```
question
  → workspace-controller  (S¹ mount + S² ceiling; reachability)
  → cypher-atomspace-gateway  (intent-routed 1–2 hop retrieval, safe subset)
  → sherlock-scout  (answer card: answer/evidence/citations/freshness/confidence/missing-info/next-actions)
  → proof-artifact-spine  (hash-chained, replayable ProofArtifact — AC-1)
operated via sherlock-shell (Matrix rooms) and agent-term (CLI); reflexively governed by fibration-node
(descent + decay; truth = what survives the loop).
```

The receipt spine's **inference arm** is live in production (receipt-gateway, prophet-platform
#1233/#1237). Runtime bindings for the rest (live HellGraph, Agent-S guest runner, live Synapse, shared
`Ledger.Push`) are tracked under epic #33.
