# Professional Workrooms

## Purpose

Professional Workrooms are the user-facing workspace layer for Professional Intelligence OS.

A workroom is the governed collaboration, evidence, task, document, meeting, agent, policy, and decision surface for a client, matter, deal, project, fund, asset, or initiative.

`prophet-workspace` owns the product semantics and UX contracts for workrooms. `prophet-platform` owns runtime deployment and platform service composition.

## Workroom types

Initial workroom types:

- client
- matter
- deal
- asset
- fund
- project
- initiative
- demo

## Required workroom surfaces

A Professional Workroom should expose:

1. Context
   - institution context pack
   - related entities
   - relationships
   - relevant history
   - source citations

2. Documents and knowledge
   - files
   - notes
   - search results
   - document summaries
   - provenance links

3. Workflow
   - playbook state
   - tasks
   - approvals
   - escalations
   - review packet or memo output

4. Agents
   - available agents
   - tool grants
   - authority boundaries
   - memory and retrieval scope
   - agent run evidence

5. Policy and obligations
   - applicable policies
   - applicable obligations
   - information barriers
   - AI-use restrictions
   - access decisions

6. Evidence and adoption
   - evidence receipts
   - policy decision receipts
   - adoption events
   - demo acceptance state
   - KPI movement

## Workroom lifecycle

```
Create -> Context Resolve -> Policy Bind -> Agent/Workflow Execute -> Review -> Evidence Seal -> Archive/Retain
```

## Integration with DelEx playbooks

DelEx playbooks should be able to create or update workrooms through a stable workspace contract.

A playbook step that mutates workspace state must provide:

- workroom id or create request;
- workroom type;
- capability id;
- policy decision reference;
- evidence receipt reference;
- adoption event reference;
- actor and authority context.

## Integration with Agent Fabric

Agents may operate inside workrooms only when:

- agent identity is registered;
- tool grants are explicit;
- memory and retrieval scopes are bounded;
- information barriers are evaluated;
- policy decisions are recorded;
- outputs are linked to evidence.

## Integration with Obligation Ledger

Workrooms should surface obligations in human and machine-readable form.

Examples:

- client confidentiality obligations;
- AI-use restrictions;
- billing and revenue rules;
- approval requirements;
- retention policies;
- wall or information-barrier constraints.

## Adoption telemetry

Every material workroom workflow should emit adoption events for:

- workflow started;
- workflow completed;
- agent output accepted;
- agent output edited;
- agent output rejected;
- human escalation;
- policy block;
- approval completed;
- playbook completion;
- demo acceptance.

## Acceptance criteria

The first Professional Workroom demo is acceptable when it can:

1. instantiate a workroom from a playbook;
2. bind institution context;
3. show policy and obligation state;
4. run or reference a governed agent step;
5. show evidence receipts;
6. emit adoption telemetry;
7. expose a review packet or memo with source citations.

## Non-goals

- Do not make workrooms a generic chat canvas.
- Do not bypass platform policy for local UX speed.
- Do not duplicate canonical contract semantics from ContractForge.
- Do not duplicate policy execution semantics from Policy Fabric.
