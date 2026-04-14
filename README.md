# prophet-workspace

`prophet-workspace` is the domain repository for the open workspace suite that will deploy **over** `SocioProphet/prophet-platform` rather than replacing it.

This repository owns:
- workspace product semantics and capability contracts
- service-level application code for mail, calendar, drive, docs, chat, and meeting surfaces
- adapter contracts for pluggable OSS backends
- local development profiles and smoke tests
- policy-aware workspace UX and admin surfaces

This repository does **not** own final cluster deployment topology. That belongs in `prophet-platform`.

## Product intent

The target is an open, governable alternative to the practical core of a modern workspace suite:
- mail
- calendar
- contacts
- file storage and sync
- collaborative documents / sheets / slides
- chat and rooms
- meetings / calling
- admin, audit, policy, and search

## Design posture

- Open protocols first: JMAP, IMAP, SMTP, CalDAV, CardDAV, WebDAV, Matrix, WebRTC, OIDC
- Pluggable substrates rather than one mandatory backend
- Policy, audit, and receipts as first-class concerns
- Explicit deployment split: product/domain here, cluster runtime in `prophet-platform`

## Repository map

- `contracts/workspace/` — capability contracts by surface
- `schemas/` — audit and receipt schemas
- `apps/` — service and UI entry points
- `profiles/local/` — local development stack definitions
- `docs/` — architecture, capability map, object model, backlog
- `tools/` — validation and tree helpers

## Relationship to Sociosphere

`SocioProphet/sociosphere` should track this repository in its workspace manifest,
registry, and topology/governance graph. This repository is the workspace product;
Sociosphere remains the meta-workspace controller.
