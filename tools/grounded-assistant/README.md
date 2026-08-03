# grounded-assistant — Virtual Assistant for Technical Support

The **product-surface slice of WO-D** (Sherlock Scout) on the
[Open Agent Continuum (ADR-0001)](../../docs/adr/ADR-0001-open-agent-continuum.md), grounded by the
receipt spine. Filed from **prophet-workspace#76 item 8** ("Virtual Assistant for Tech Support —
Q&A / Parts / Service-Request / Warranty bot agents").

This is **our sovereign surface** — a set of domain-scoped support bots, spec-as-code. It is **not** a
vendor of IBM Watson Assistant. It is Sherlock's grounded-agent product wearing a tech-support face.

## What it is

Five purpose-built support bots (transcribed from the reference UI). Each is a domain-scoped grounded
agent: it gathers client info, answers from its domain knowledge, and can only answer in the
Sherlock-Scout answer-card shape with a receipt.

| Bot | domain | skill | required client fields |
|---|---|---|---|
| Question & Answering | product-knowledge | grounded-qa | product_model |
| Question & Answering Flex | product-knowledge | grounded-qa-flex | product_model, issue_summary |
| Parts Replacement | parts-catalog | parts-lookup | product_model, part_id |
| Check Service Request Status | service-requests | service-request-status | service_request_id |
| Warranty Check | warranty-registry | warranty-lookup | product_serial |

Instances: [`bots.json`](bots.json). Descriptor + gate: [`assistant_bot.py`](assistant_bot.py).

## The two contracts

1. **AssistantBot descriptor** (`schemas/assistant-bot.schema.json`) — `id`, `domain`, `skill`,
   `requiredClientFields`, and an `agentSpecRef` mapping the bot to an **agent-registry AgentSpec**
   principal. Bots enter as *external* principals, so the spine caps them at the `Derived` epistemic
   ceiling (STAR-1 / AC-2).
2. **Grounded answer card** (`schemas/grounded-answer-card.schema.json`) — the answer contract. It
   **reuses the Sherlock-Scout answer-card shape**
   (`sherlock-search/docs/evidence-answer-contract.md`): `answer` + `evidence` (refs) + `citations` +
   `freshness` + `confidence` + `missingInfo` + `nextActions`, plus a **`receipt`** (a ProofArtifact
   from the estate spine). We do not re-derive the shape.

## Teeth (the gate)

`answer(bot, client, draft, ledger)` enforces, in order:

1. **required client fields** for the intent must be gathered → else `missing-fields`.
2. **grounding**: ≥1 evidence ref **and** ≥1 citation → else `ungrounded`.
3. **confidence floor** (0.60): below it the bot must abstain, not guess → else `low-confidence`.
4. **receipt law (AC-1)**: a ProofArtifact MUST be emitted on the spine, fail-closed → else
   `receipt-required`. *An answer that cannot emit a receipt is not an answer.*

A grounded answer with evidence + receipt **passes**; an ungrounded one (no evidence / no citation / no
receipt / confidence below floor) is **rejected**; a bot missing required client fields is **rejected**.

## Consume-not-fork

- Receipt spine — imports `publish`/`RunPackage` from [`../proof-artifact-spine`](../proof-artifact-spine)
  (WO-B). Same hash-chained ledger (canonical JSON + SHA-256, the FIPS-180-4 algorithm), same AC-1.
- Answer-card shape — Sherlock's evidence-answer contract in `sherlock-search`.
- Bot identity — agent-registry `AgentSpec` / `AgentPassport` principals.

## Run the teeth

```bash
python3 tests/grounded_assistant_test.py   # 14/14, teeth both ways, no pytest dep
```

## Runtime follow-up (tracked + assigned)

Spec-as-code lands here; the live runtime is filed as issues (see prophet-workspace#76, ADR-0001):
live Matrix rooms per bot (Sherlock Shell / wordops-matrix chatops), live knowledge grounding per
domain, and the per-bot grounded skills. This module is the contract + a runnable reference.
