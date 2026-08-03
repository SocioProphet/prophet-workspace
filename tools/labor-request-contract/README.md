# labor-request-contract (prophet-workspace#108)

The **request-centric labor loop** as spec-as-code — the estate integration of the *SocioProphet Labor
Network Charter v0.1* into the Agora / work-knowledge plane.

## The thesis it encodes

The charter's core operating statement:

> **labor = request + response + evidence + fulfillment + trust** — *not* identity + feed + ambient
> messaging + attention.

This module makes that a **contract with teeth**. It does not reinvent estate machinery — it *consumes* it:

| Charter concept | Estate primitive consumed (not forked) |
|---|---|
| evidence + fulfillment are *recorded* | receipt spine — WO-B `proof-artifact-spine` (ADR-0001). Every stage emits a hash-chained `ProofArtifact`. |
| evidence is *graded* | metadata-standards `evidence_grade` E1..E5 (E3+ ⇒ null hypotheses). |
| trust is *epistemic standing*, not popularity | GKN Standing Vector — `guild-knowledge-network` (guild-scoped, min-threshold). |

## The chain

```
LaborRequest ──▶ LaborResponse ──▶ Evidence ──▶ Fulfillment ──▶ TrustBinding
   (ask)           (respond)      (evaluate)     (deliver)     (update trust)
     └──────────── every stage is receipted on the estate receipt spine ────────────┘
```

Canonical loop (charter §6): **Ask → Route → Respond → Evaluate → Award → Deliver → Update trust.**

## The teeth (feed / vanity model rejected by construction)

`verify_labor_chain()` in `labor_contract.py` enforces:

| ID | Law | Rejects |
|---|---|---|
| LC-1 | chain integrity | a response/evidence/fulfillment/trust that does not link back through the request |
| LC-2 | receipt law (AC-1) | any stage with no spine receipt, or a receipt that does not resolve on the ledger |
| LC-3 | evidence law (LN-005/§7) | a fulfillment citing **no evidence**; E3+ evidence with **no null hypotheses** |
| LC-4 | trust = standing (charter core / LN-009) | a **raw popularity scalar** (followers/likes/score/…) or a **non-guild-scoped / global** standing ref |
| LC-5 | compensation transparency (LN-004) | a **hidden-compensation** request that is not explicitly comp-exempt |

So: a request → response → fulfillment with graded evidence + a spine receipt + a guild-scoped GKN
standing binding **VERIFIES**; a fulfillment with no evidence / no receipt, or a "trust" that is a
popularity number rather than epistemic standing, is **REJECTED**.

## Pieces

| File | Role |
|---|---|
| `labor_contract.py` | the 5 typed market objects, `verify_labor_chain()` (the teeth), `run_labor_loop()` (reference driver that receipts every stage on the spine). |
| `tests/labor_contract_test.py` | 14 checks, teeth both ways. Run: `python3 tests/labor_contract_test.py`. |
| `../../contracts/labor/*.schema.json` | the declarative object contracts (LaborRequest / LaborResponse / Evidence / Fulfillment / TrustBinding + ReceiptRef). |
| `../../contracts/labor/examples/*.json` | one valid chain bundle + invalid bundles exercising each tooth. |
| `../validate_labor_contract.py` | validates examples against schemas **and** drives the chain teeth (CI entrypoint). |

## Follow-up (tracked)

The **product surface** — the labor-network UI / marketplace shell (charter §9: Requests · Matches ·
Work · Learn · Trust · Contracts · Governance) — is filed as a follow-up. This module is the contract
the surface must satisfy. Cross-ref prophet-workspace#108, GKN#9 (epistemic-not-popularity standing).
