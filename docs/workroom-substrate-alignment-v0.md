# Workroom Substrate Alignment v0

Status: draft alignment note  
Authority repo: `SocioProphet/prophet-workspace`  
Claim level: product architecture / control contract; no runtime implementation change  
Scope: Professional Workroom alignment to recovered privacy, memory, topic, audio, transport, estate, and learning surfaces

## Purpose

This note aligns Professional Workrooms with the recovered SocioProphet substrate doctrines and authority surfaces.

`prophet-workspace` owns workspace product semantics and UX contracts. It does not own final runtime deployment topology, ontology authority, policy execution, transport protocol authority, model governance, or estate coordination. Those remain in their respective repos.

The goal is to make Professional Workrooms the user-facing orchestration surface without collapsing authority boundaries.

## Existing boundary

The current Professional Workrooms contract already establishes that a workroom is the governed collaboration, evidence, task, document, meeting, agent, policy, and decision surface for a client, matter, deal, project, fund, asset, or initiative.

This alignment note adds the recovered substrate constraints that must be respected before implementation deepens.

## Workroom substrate stack

A Professional Workroom should be treated as a product surface over these substrate roles:

| Substrate | Authority repo | Workroom use |
| --- | --- | --- |
| Workroom product semantics | `SocioProphet/prophet-workspace` | Workroom types, UX contracts, workspace objects, office artifacts, review packets. |
| Runtime deployment / services | `SocioProphet/prophet-platform` | Service composition, deployment, telemetry, platform runtime. |
| Meta-workspace topology | `SocioProphet/sociosphere` | Cross-repo topology, workspace materialization, recovery map, governance graph. |
| Repository estate ledger | `SocioProphet/workspace-inventory` | Authority surfaces, adoption state, validation posture, drift review. |
| Privacy / memory doctrine | `SocioProphet/ontogenesis` | DoNotLearn / DoNotLink, governed memory strata, semantic promotion boundaries. |
| Topic membranes | `SocioProphet/slash-topics` | Topic packs, source scopes, policy membranes, topic execution receipts. |
| Audio-first review | `SocioProphet/speechlab` | Audio events, transcripts, sectioned review, corrections, confusability fixtures. |
| Agent execution | `SocioProphet/agentplane` | Action proposals, tool grants, execution evidence, replay, receipts. |
| Agent identity / registry | `SocioProphet/agent-registry` | Agent identity, authority, capability declaration, revocation. |
| Policy / guardrails | `policy-fabric` / `guardrail-fabric` | Policy decisions, guardrail results, admissions, denials, reviews. |
| Model governance | `SocioProphet/model-governance-ledger` | Inference, evaluation, drift, learning, privacy, and memory receipts. |
| Transport candidate | `SocioProphet/TriTRPC` | Candidate typed control-plane framing for future workroom events; not required yet. |
| Institutional learning | `SocioProphet/systems-learning-loops` | Lessons, patterns, receipts, teaching objects from workroom failures and successes. |

## Workroom object responsibilities

A workroom object should not directly own all substrate state. Instead, it should carry references.

Minimum reference classes:

- `contextRefs` for source-backed context packs;
- `topicPackRefs` for slash-topic membranes;
- `policyDecisionRefs` for policy and guardrail decisions;
- `memoryScopeRefs` for memory and retrieval boundaries;
- `privacyDecisionRefs` for DoNotLearn / DoNotLink admissions;
- `agentRunRefs` for agent steps and evidence;
- `receiptRefs` for runtime, privacy, learning, model, and topic receipts;
- `officeArtifactRefs` for generated or attached documents;
- `audioReviewRefs` for speechlab-managed transcript/review/correction artifacts;
- `adoptionEventRefs` for completion, acceptance, edit, rejection, escalation, and demo telemetry.

## Memory and privacy constraints

Professional Workrooms must treat memory as governed representation strata.

The following are forbidden without explicit policy admission and receipts:

- turning source context into durable memory;
- converting transcripts into vector memory;
- treating search results as admitted claims;
- turning topic membership into an identity link;
- allowing agent output to become reusable context without review;
- linking workrooms through latent/vector proximity;
- carrying private context across client, matter, deal, fund, or project boundaries.

Required boundary questions:

1. Is this artifact raw signal, anchor, evidence, claim, graph relation, statistical feature, vector candidate, learned latent state, policy, action, receipt, or teaching object?
2. Is this operation learning, linking, both, or neither?
3. Which policy decision admits it?
4. Which receipt proves the decision was enforced?
5. What expires, revokes, or supersedes it?

## Topic membrane constraints

A workroom may use slash-topics as governed topic-pack membranes.

A topic pack may scope search, knowledge, source access, display behavior, and policy posture. It must not become implicit memory permission or implicit identity linkage.

A workroom using a topic pack should record:

- topic pack id and version;
- source scope;
- evidence requirements;
- policy binding;
- allowed operators;
- integration boundaries;
- topic execution receipt;
- redaction/quarantine/review state.

## Audio-first review constraints

A workroom may contain audio review artifacts, but speechlab owns the audio-first review doctrine.

A workroom should not treat transcription as memory permission. It should keep correction events explicit and link spoken teaching objects only after review.

Required audio references:

- audio source or event ref;
- transcript artifact ref;
- audio anchor or timestamp selector;
- sectioned review object ref;
- correction event refs;
- audio review receipt;
- memory or teaching decision ref.

## Agent execution constraints

Agents may operate inside workrooms only when:

- agent identity is registered;
- tool grants are explicit;
- memory and retrieval scopes are bounded;
- topic membranes are declared where relevant;
- information barriers are evaluated;
- policy decisions are recorded;
- outputs are linked to evidence;
- effectful actions emit receipts;
- adoption events are emitted when human review accepts, edits, rejects, or escalates output.

## Professional versus general workrooms

A general workroom can coordinate collaboration.

A Professional Workroom must add professional-grade controls:

- client/matter/deal/project authority context;
- obligation and policy state;
- evidence receipts;
- source citations;
- review packet or memo output;
- adoption telemetry;
- retention and archive posture;
- information barriers;
- agent authority boundaries;
- audit-ready receipt surfaces.

## Acceptance criteria for next implementation tranche

The next workroom implementation tranche should not attempt all integrations at once.

Minimum useful tranche:

1. Extend or review `contracts/workspace/professional-workroom.schema.json` against this alignment note.
2. Add explicit optional reference fields for topic packs, privacy decisions, memory scopes, audio review, and learning receipts if missing.
3. Add one example workroom showing these refs without requiring runtime implementations.
4. Validate the example locally.
5. Keep runtime service work in `prophet-platform` separate from product contract work here.

## Non-goals

This note does not implement workrooms, add UI, change runtime deployment, define TriTRPC schemas, define policy logic, choose a memory store, choose ASR/TTS models, or make slash-topics mandatory.

It also does not make `prophet-workspace` the authority for Ontogenesis, AgentPlane, Policy Fabric, Model Governance Ledger, Speechlab, Slash Topics, or Sociosphere.

## Claim boundary

This is a product-architecture alignment note. It makes recovered doctrines usable by the workroom product surface without claiming runtime readiness or collapsing authority boundaries.
