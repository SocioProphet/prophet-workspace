# OrgGov Control Room

## Purpose

The OrgGov Control Room is the Prophet Workspace product surface for Organization Governance Control Plane v0.

It makes the institutional work loop visible:

```text
Objective → Workroom → Actor → Role → Policy → Asset → Action → Evidence → Review → Outcome → Score → Learning
```

## Product posture

This is not a generic task board and not a chat-first surface. It is a governed control room for human-agent institutional work.

The user should be able to answer:

- What objective are we pursuing?
- Which work orders are active?
- Which human and agent actors are involved?
- What roles and authority do they hold?
- Which policies and constraints apply?
- Which assets are in scope?
- What actions happened or are pending?
- What evidence supports the outcome?
- Who reviewed it?
- What was the outcome?
- How did we score it?
- What should the system learn next?

## Contract files

- `contracts/workspace/orggov-control-room.schema.json`
- `contracts/workspace/orggov-control-room.v0.1.example.json`

## Relationship to Professional Workrooms

Professional Workrooms remain the durable workspace container. The OrgGov Control Room is a specialized view over a workroom that binds objectives, actors, policies, assets, actions, evidence, reviews, outcomes, scorecards, and learning events into one visible loop.

## Estate bindings

- Platform contract: `SocioProphet/prophet-platform#406`
- Workspace workstream: `SocioProphet/prophet-workspace#15`
- Ontology slice: `SocioProphet/ontogenesis#39`
- Agent authority binding: `SocioProphet/agent-registry#18`
- Policy gates: `SocioProphet/policy-fabric#57`
- Execution evidence: `SocioProphet/agentplane#104`
- Model/data/tool receipts: `SocioProphet/model-governance-ledger#13`
- Estate topology: `SocioProphet/sociosphere#272`
- Scorecards: `SocioProphet/delivery-excellence#14`
- Evidence search: `SocioProphet/sherlock-search#36`
- Local-first state evidence: `SourceOS-Linux/sourceos-syncd#13`

## v0 acceptance

The v0 control room is acceptable when the fixture can show the dogfood work order for `prophet-platform#406`, link to the merged platform and ontology PRs, and preserve references for authority, policy, evidence, outcome, score, and learning panels.
