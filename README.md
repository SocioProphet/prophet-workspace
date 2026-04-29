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

## Professional Workrooms

Professional Workrooms are the first Professional Intelligence OS workspace contract surface.

Contract and example:
- `contracts/workspace/professional-workroom.schema.json`
- `contracts/workspace/professional-workroom.v0.1.example.json`

Validate locally:

```bash
python3 tools/validate_professional_workrooms.py
```

The workflow `.github/workflows/professional-workrooms.yml` runs this validation when the workroom contract, example, validator, or workflow changes.

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
