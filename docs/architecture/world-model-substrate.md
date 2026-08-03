# The Layer-1 World-Model Substrate — canonical, reconciled definition

- **Owner:** @mdheller
- **Status:** active
- **Last reviewed:** 2026-08-03
- **Version:** 0.1
- **Related ADRs:** [ADR-0002](../adr/ADR-0002-governed-cognition-functor.md) (§4 L1), [ADR-0001](../adr/ADR-0001-open-agent-continuum.md) (§6, §9.7)
- **Closes doctrine half of:** prophet-workspace#86 (ADR-0002 GAP-4). Cross-ref prophet-workspace#76 (item 4).
- **Epistemic status:** `Derived` — this reconciles doctrine already written across the estate into one checkable reference. It ships the descriptor contract + validator (teeth) and the single canonical definition; it does **not** claim the topological constructs are implemented or the falsification harness has run. Those remain follow-up (see §5).

---

## 1. Why this doc exists

ADR-0002 §4 (L1) names the estate's **World-Model substrate**

```
W = (S_dur, S_act, Θ, T, C, Π, E)
```

plus four structural attributes — the primitive **order cycle S¹ + lift τ**, the recursive **Hopf tower H0..H3**, the **dual-sector decomposition V⁺ (manifest) / V⁻ (latent)**, and the **balance observable M(Ψ)**. Until now these lived only as prose, scattered across the superconscious doctrine, the ProCybernetica semantic algebra, the three-time model, and the receipt spine. There was **no single reconciled, checkable definition** — GAP-4.

This page is that single definition, and it is backed by a machine-checkable descriptor contract (`schemas/world-model-substrate.schema.json`) with a fail-closed validator (`tools/validate_world_model_substrate.py`). A substrate declaration that names all seven components with resolvable mechanism bindings **verifies**; one missing a component, carrying an unknown component, or pointing at a dangling mechanism **is rejected**.

---

## 2. The reconciliation that GAP-4 required (symbol assignment)

The ADR-0002 §4 L1 table listed two rows with **swapped symbols** relative to the canonical tuple: it described "**Order structure T** (valid_time/system_time)" and "**Transition algebra Θ**", while the tuple `W = (S_dur, S_act, Θ, T, C, Π, E)` and the reference diagram read Θ before T. GAP-4 exists precisely to make the doctrine coherent, so this page fixes the assignment **canonically**:

| Symbol | Canonical meaning (this page) | Note |
|---|---|---|
| **Θ (Theta)** | **order bundle** — the order structure / order cycle S¹ + lift τ / monodromy framing over the semantic coordinate | consolidates the ADR's separate "Order structure" and "Order cycle S¹" doctrine rows under one symbol |
| **T** | **transition algebra** — the operators that carry W from state to state | the orchestrator/agent transitions |

The descriptor contract and validator encode **Θ = order, T = transition**. Any consumer of the ADR should read the L1 table's "Order structure T" / "Transition algebra Θ" labels as reconciled to this assignment.

---

## 3. The seven components — each bound to its owning estate mechanism

Every component of W is bound to a real estate mechanism via a `mechanismRef` (an `estate://<repo>/<path>` reference drawn from the closed registry in the validator). The canonical binding:

| Component | Meaning | Owning mechanism (`mechanismRef`) | Verdict |
|---|---|---|---|
| **S_dur** | durable state — canonical persisted world state | `prophet-workspace/tools/cypher-atomspace-gateway` (AtomSpace canonical + Cypher façade; HellGraph store) | HAVE |
| **S_act** | active state — working/valid-time projection (three-time model) | `prophet-platform/apps/regis-acr-api/src/regis_acr_api/er_spine.py` (`valid_time`/`system_time`; also `regis-entity-graph/schemas/node.schema.json`) | PARTIAL |
| **Θ** | order bundle — order structure / order cycle S¹ + lift τ | `ProCybernetica/procyber/semantic/agent_coordinate_vector.py` (11-axis `AgentCoordinateVector`, exactly-one-primary) | PARTIAL |
| **T** | transition algebra — state-to-state operators | `sp-orchestrator/crates/sp-exec/src/exec.rs` (orchestrator DAG) | PARTIAL |
| **C** | constraint family — admissibility constraints on W | `policy-fabric/contracts` (policy contracts stand in for a substrate constraint algebra) | PARTIAL |
| **Π** | projection family — lift/ground between abstraction layers | `ProCybernetica/procyber/semantic/semantic_algebra.py` (`lift ⊣ ground` adjunction, §8) | HAVE |
| **E** | evidence layer — append-only, tamper-evident receipt spine | `prophet-workspace/tools/proof-artifact-spine` (hash-chained `ProofArtifact`, `publish()=f_!`, AC-1) | HAVE |

Reconciliation to the source doctrines requested by #86:
- **three-time model** — S_dur/S_act correspond to the durable (system_time) / active (valid_time) axes of the bitemporal `er_spine.py`; the third (decision) time axis is still absent (GAP-2, pw#84).
- **semantic-coordinate** — the order structure Θ and the projection family Π are the `AgentCoordinateVector` + `lift ⊣ ground` adjunction in ProCybernetica's semantic algebra.
- **receipt spine** — the evidence layer E is the four-arm receipt spine; the knowledge arm (`proof-artifact-spine`) is the substrate-local binding (ADR-0002 §7).

---

## 4. The four structural attributes

| Attribute | Canonical form | Owning mechanism (`mechanismRef`) | Status |
|---|---|---|---|
| **Order cycle S¹ + lift τ** | the circle / monodromy framing of the order structure, with lift operator τ (`lift ⊣ ground`) | `ProCybernetica/procyber/semantic/semantic_algebra.py` | PARTIAL — `lift` exists; literal S¹/monodromy framing is doctrine-only |
| **Hopf tower H0..H3** | the recursive four-level tower | `superconscious/docs/doctrine/semantic-address-algebra-as-spectral-field-skeleton.v0.1.md` (doctrine carrier; "does not host the code") | PARTIAL (doctrine-only) |
| **Dual-sector V⁺/V⁻** | V⁺ manifest, V⁻ latent | `ProCybernetica/procyber/semantic/spectral_grounding.py` (spectral-field math) | PARTIAL (doctrine-only) |
| **Balance observable M(Ψ)** | scalar balance over world-model state Ψ | `ProCybernetica/procyber/semantic/spectral_grounding.py` | PARTIAL (doctrine-only) |

Per ADR-0002 and ADR-0001 §9.7, the **literal Hopf-tower / dual-sector / M(Ψ) terminology is not yet named/tested in code**, and the superconscious **falsification harness has not run**. These constructs must stay out of external material until it passes. superconscious is **reference-only** here; this doc does not modify it.

---

## 5. What this closes, and what remains (follow-up @mdheller)

**Closed by this PR (the doctrine + descriptor half of GAP-4):**
- One canonical, reconciled definition of W and its four structural attributes (this page).
- A machine-checkable `WorldModelSubstrate` descriptor contract (schema + validator) that names all seven components, binds each to an owning mechanism, and declares the structural attributes — with teeth both ways.

**Remaining (each to be filed as follow-up):**
1. **Live binding of each mechanism** — wire each `mechanismRef` to a runtime probe so a declaration's verdicts are *measured*, not asserted (currently the registry resolves references; it does not execute them).
2. **Name/test the topological constructs in code** — implement or explicitly demote the Hopf tower / dual-sector / M(Ψ) constructs in `spectral_grounding.py`, and **run the superconscious falsification harness** (ADR-0001 §9.7). This is the second half of #86 and stays owned by superconscious/ProCybernetica.
3. **Substrate constraint algebra (C) and transition algebra (T)** as first-class objects over W, rather than policy contracts / orchestrator code standing in.

---

## 6. Verify (teeth)

```sh
python3 tools/validate_world_model_substrate.py
# OK: WorldModelSubstrate validation passed (schema in lockstep, 1 example verified, 3 invalid rejected)
```

- **Verifies:** `examples/world-model-substrate.example.json` — all seven components, valid mechanism bindings, four structural attributes.
- **Rejected:** `…missing-component.invalid.json` (drops E), `…unknown-component.invalid.json` (adds a bogus `Q`), `…dangling-ref.invalid.json` (a `mechanismRef` outside the registry).

The receipt-spine and hash-chained integrity of E use **SHA-256, the FIPS-180-4 approved hash algorithm** (an algorithm choice, not a FIPS-140 module claim; see ADR-0002 §7).
