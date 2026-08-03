# Sherlock Shell — Matrix Room Administration Runbook

- **Owner:** @mdheller
- **Status:** active
- **Last reviewed:** 2026-08-03
- **Version:** 0.2
- **Related services:** sherlock-shell, sherlock-search, sherlock-cases, receipt-gateway, prophet-workspace (workspace controller), lampstand
- **Related ADRs:** [ADR-0001 Open Agent Continuum](../adr/ADR-0001-open-agent-continuum.md), SP-ARCH-004
- **Related runbooks:** room-recovery-drill, e2ee-key-escrow-drill, bridge-outage, rogue-bot-containment, legal-hold-export (see §14 — to be written)

> **Enhancement note (v0.2).** This extends the base runbook with the three bindings that make it part of the continuum rather than a standalone Matrix guide: (a) rooms are the **operator surface of the SP-ARCH-004 workspace controller** — a room's bot powers are a projection of a mount table, not ad-hoc grants; (b) every irreversible bot action is a **`publish` (`f_!`)** and MUST emit a receipt/ProofArtifact; (c) the **OS support/help features** (SourceOS help surfaces) consume these rooms as their control plane, so room classes and power levels are a stability contract, not cosmetic.

## 1. Operating assumptions

Sherlock Shell on Matrix is the **authoritative human control plane**, not the system of record. `sherlock-cases` and `sherlock-search` remain authoritative; rooms **project** state and **collect approvals**. Every approval collected in a room is a workspace `publish` and is receipted (AC-1 of ADR-0001).

## 2. Topology

### 2.1 Space hierarchy
- `#sherlock:<server>` — parent space
- `#sherlock-triage` — intake · `#sherlock-ops` — platform ops · `#sherlock-watchlists` — alerts/world-state · `#sherlock-ingestion` — connector/corpus events
- `#cases-p1`, `#cases-p2`, `#cases-vendor` — severity/domain queues
- one room per active case, nested under its queue subspace

### 2.2 Room classes
1. **Control** (triage, ops, watchlists, ingestion) 2. **Queue** (severity/domain) 3. **Case** (one active case) 4. **Admin** (restricted maintenance) 5. **Bridge** (external ingress/egress)

## 3. Naming convention
- Spaces: `#sherlock[-subspace]:server` · Queue: `#cases-{severity|domain}:server` · Case: `#case-{case_id}-{slug}:server` · Bridge: `#bridge-{network}-{purpose}:server`
- Rules: case id immutable once assigned; room topic MUST contain canonical case URL + state summary; aliases MUST NOT encode confidential customer names unless the server is private and policy permits.

## 4. Power levels (the mount table, projected)

> **Binding:** a bot's power level in a room is the room-scoped shadow of its workspace **mount authority**. Widening a bot's powers = widening a mount table = **Layer 2**, requires sign-off (SP-ARCH-004 WS-5). Narrowing is Layer 1. The room ACL and the mount table must not disagree; if they do, the mount table wins and the room is reconciled.

Personas: Server-admin (homeserver only) · Space-steward (layout/queue structure) · Room-admin · Moderator · Operator · Bot (Sherlock, Hookshot, bridges) · Auditor (read-only).

Suggested levels: default member `0`; operator `0` unless specific need; bot service user `50`; moderator `50`; room-admin `100`; space-steward `100` in parent, `50/100` in child.

Restricted to moderators/admins: invite, change settings, remove/ban, redact others, change avatar/name/topic, modify widgets, room-wide notifications, upgrade room, change history visibility, change server ACLs, enable encryption.

## 5. Encryption stance
- **Unencrypted operational rooms** — where bridges/webhooks/server-side export are operationally mandatory (triage, ingestion, GitHub/Jira/vendor webhook rooms).
- **Encrypted restricted rooms** — high-sensitivity internal coordination where bot/bridge behavior is verified. Do not assume all bots/bridges participate cleanly; encrypted rooms require key-management discipline (§14 escrow drill).

## 6. Room creation checklist (case room)
1. create under proper queue space · 2. set canonical alias · 3. set topic with case metadata · 4. set history visibility · 5. access = invite-only or restricted-to-space-members · 6. promote service bot(s) to required level · 7. pin the state card (§12) · 8. attach widgets only if needed · 9. register room id in `sherlock-cases` DB · 10. register audit retention/export policy · **11. (continuum) register the room's workspace binding so its bot powers derive from a mount table, and confirm the receipt sink is reachable** (the room's approvals must be publishable).

## 7. Restricted-join model
Prefer `restricted`/space-member join for internal rooms. Public directory visibility OFF by default. Directory-visibility and public-joinability are **separate controls** — treat independently.

## 8. Ownership transfer & recovery
- **Normal:** admin promotes successor → successor confirms → original demotes self only after confirmation.
- **Abandoned:** use homeserver admin API to inspect room state and restore an active admin (server-admin action, not room-admin).

## 9. Upgrades & tombstoning
Plan/announce upgrades; update parent-space references; tombstone + lock the old room. Case rooms should almost never be upgraded mid-incident unless a protocol/security issue forces it.

## 10. Bots & bridges
- **Sherlock bot:** case create/update/triage, search + evidence cards, approval workflows, watchlist alerts, room state refreshes, escalation. Every irreversible capability is a receipted `publish`.
- **Hookshot:** GitHub/GitLab/Jira/webhook ingress; keep isolated from privileged admin rooms.
- **Bridge policy:** dedicated bridge rooms (not org-wide bridging); treat bridged rooms as lower-trust; prefer one-way ingress for noisy systems; explicit approval before any bidirectional bridge; validate webhook signatures + keep replay-protection logs.

## 11. Retention & export
Case: JSON + attachments snapshot on close. Queue: rolling export + weekly compaction. Ops: scheduled export + incident bookmarks. Encrypted: export only via approved key-management process.

## 12. State card pinned in every case room
case id · tenant/org id · severity · status · owner · SLA clock · last evidence refresh · linked corpus/project ids · linked external ticket ids · latest recommendation summary · approval requirements · **last trace id / ProofArtifact ref** (the receipt of the last publish).

## 13. OS support/help integration (SourceOS)
SourceOS help/support features use these rooms as their control plane: a user's in-OS "get help" opens (or routes to) a Sherlock room; the help agent answers via Sherlock Scout (grounded, receipted); escalations become cases. Therefore **room classes, aliases, and power levels in this runbook are a stability contract for the OS** — changing them is an ADR-worthy decision (anti-pattern: undocumented room aliases / undocumented bot powers).

## 14. Admin runbooks still to write (tracked)
room-recovery drill · E2EE key escrow/recovery drill · bridge outage procedure · spam/abuse/rogue-bot containment · legal hold & export workflow · alias & room-directory governance. Each becomes a `docs/ops/*.md` page with the standard metadata header.
