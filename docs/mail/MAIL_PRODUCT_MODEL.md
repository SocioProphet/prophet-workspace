# Mail Product Model

## Positioning

Prophet Mail is **Hey! meets Superhuman meets Gmail**.

- **Hey!** contributes the routing philosophy: the inbox is earned, not defaulted. Screener controls who gets in. Feed and Paper Trail separate signal from noise at the source.
- **Superhuman** contributes the speed and intelligence layer: keyboard-first, AI triage at every turn, split inbox, memory-backed replies, reply drafts, read receipts.
- **Gmail** contributes the foundation: labels-not-folders, conversation threading, SMTP/IMAP backbone, search-first navigation, deep Workspace integration.

The foundation is the same for all three. The differentiation is in the routing model and intelligence layer on top.

## Core concepts

### Routing model (Hey!-style)

Every message is routed to a slot before the user sees it:

| Slot | What goes there |
|---|---|
| **Imbox** | Mail that earned its place — people you know, things that need you |
| **Feed** | Newsletters, digests, subscriptions — read when you want |
| **Paper Trail** | Receipts, confirmations, order notifications — reference, not action |
| **Screener** | New senders awaiting a single decision: allow / block / route-to-feed |
| **Set Aside** | Deliberately parked for later |
| **Reply Later** | Needs a reply, not now |

Routing is AI-assisted by default. The screener fires for any sender not already in Contacts or previously replied-to. One decision per sender, never asked again.

### Labels (Gmail-style, extended)

Labels are semantic tags, not folders. A message can carry many. Four label classes:

- **system** — built-in slots (imbox, feed, paper_trail, archive)
- **user** — manually created
- **ai_suggested** — provisional AI tags, status=PROPOSED until confirmed
- **topic** — aligned to the 22-topic TriTRPC canon via `topicCode`

The topic label class is the bridge to the broader SP intelligence layer — a mail thread about a policy matter gets `[pol]`, a thread about a system incident gets `[inc]`. This enables cross-surface search and memory-mesh recall across mail, docs, and workrooms.

### Intelligence layer (Superhuman-style)

Every message gets:
- **AI summary** — one sentence, generated at receipt
- **Routing suggestion** — slot + confidence
- **Reply draft** — context-aware, memory-mesh backed
- **Topic tags** — 22-topic vector if content warrants
- **Triage receipt** — every AI action emits a `MailTriageReceipt` before applying

All AI actions are policy-gated and auditable. The receipt is the evidence path.

### Memory recall

Before composing or drafting a reply, the system pulls memory-mesh context for the sender and thread subject. The `memoryRef` on the message links the recalled context so the draft is grounded in prior interactions, not just the current message.

## Schema inventory

| Schema | Purpose |
|---|---|
| `mail-message.schema.json` | Canonical message record |
| `mail-thread.schema.json` | Conversation grouping |
| `mail-label.schema.json` | Semantic tag with lifecycle |
| `mail-screener.schema.json` | Per-sender trust decision |
| `mail-inbox-profile.schema.json` | Per-account routing + AI configuration |
| `mail-account-binding.schema.json` | IMAP/SMTP/Google/Exchange adapter binding |
| `mail-triage-receipt.schema.json` | Evidence record for every AI/automated action |

## Backend

- **Transport:** IMAP/SMTP (universal), Google Workspace API, Microsoft Exchange/365
- **Search:** Sherlock (shared with docs/workspace search)
- **AI:** Prophet Platform AI action layer
- **Memory:** memory-mesh recall-before-action + writeback-after-action
- **Storage:** fogstack-drive (attachments), SemanticCell store (message index)
- **Contacts:** shared Contacts surface (see `contracts/contacts/`)

## Cross-surface integration

Mail is not a silo. Key integration points:

- **Drive:** attachments saved to Drive; Drive files linked inline
- **Workrooms:** threads linked to professional workrooms; context shared
- **Tasks:** "Create task from thread" action via `MailTriageReceipt(actionType=create_task)`
- **Calendar:** meeting invites parsed and surfaced in Calendar
- **Contacts:** sender resolution and enrichment
- **Sherlock:** mail threads indexed and searchable alongside docs, tasks, and workspace artifacts

## Open work

- [ ] IMAP/SMTP adapter implementation (`prophet-platform`)
- [ ] Google Workspace Mail adapter (`prophet-platform`)
- [ ] Exchange/365 adapter (`prophet-platform`)
- [ ] Screener UI surface (`prophet-workspace` frontend)
- [ ] AI triage pipeline wiring (`prophet-platform`)
- [ ] Memory-mesh recall integration (`memory-mesh`)
- [ ] Sherlock mail index connector (`sherlock-search`)
- [ ] Contacts schema + integration (`contracts/contacts/`)
- [ ] Calendar invite parsing (`contracts/calendar/`)
- [ ] Keyboard shortcut spec (Superhuman parity)
- [ ] Read receipt implementation
- [ ] Exodus migration path for Gmail and Exchange imports
