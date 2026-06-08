# Exodus Migration Workroom bridge

Status: synthetic demo bridge v0.

Related umbrella issue: `SocioProphet/sociosphere#478`.

## Purpose

The Exodus Migration Workroom bridge lets a Prophet Workspace `ProfessionalWorkroom` carry a synthetic Exodus exit-readiness run without forking the core workroom model.

The bridge is deliberately thin:

- `ProfessionalWorkroom` remains the canonical workspace containment surface.
- `ExodusWorkroomBridge` binds a workroom to an Exodus run and its domain-specific artifacts.
- Exodus remains responsible for migration topology, evidence, scoring, blockers, recommendations, and budget proposal records.
- Sociosphere remains responsible for cross-repo control-plane orchestration and durable governance state.

## Files

- `contracts/workspace/exodus-workroom-bridge.schema.json`
- `contracts/workspace/exodus-workroom-bridge.v0.1.example.json`
- `contracts/workspace/exodus-migration-workroom.v0.1.example.json`
- `tools/validate_professional_workrooms.py`

## Demo boundary

The current bridge references the synthetic Exodus run merged in `SocioProphet/exodus` PR #18.

The demo uses fixture data only. It does not use live Apple, Google, or Microsoft credentials. It does not call live provider APIs. It does not write to provider accounts. It does not claim production migration readiness or UI readiness.

## Workroom mapping

The example Professional Workroom carries Exodus context through existing generic ref fields:

| ProfessionalWorkroom field | Exodus meaning |
|---|---|
| `contextRefs` | Exodus run, tenant, and Sociosphere issue refs |
| `evidenceRefs` | Exodus export ledger and evidence records |
| `providerCaptureRefs` | Provider topology refs |
| `providerProjectionRefs` | Representative asset census refs |
| `officeArtifactRefs` | Readiness report, export ledger, and budget proposal artifacts |
| `runtimeBindingRefs` | Synthetic offline boundary |
| `semanticReceiptRefs` | Semantic receipt for the Exodus run context |
| `tasks` | Review actions for scores, evidence, and budget waves |

The bridge contract holds the full Exodus-specific binding:

- `exodusRunRef`
- `providerTopologyRefs`
- `accountRootRefs`
- `assetCensusRefs`
- `exportLedgerRefs`
- `scoreRefs`
- `blockerRefs`
- `recommendationRefs`
- `budgetProposalRef`
- `officeArtifactRefs`
- `evidenceRefs`
- `policyRefs`
- `controlPlaneRefs`

## Validation

Run:

```bash
python3 tools/validate_professional_workrooms.py
```

The validator checks that:

- the existing Workroom, Professional Workroom, Office Artifact, channel, and crossing examples still validate;
- the Exodus Professional Workroom validates against the Professional Workroom schema;
- the Exodus bridge validates against the bridge schema;
- the bridge points to the Exodus Professional Workroom;
- the bridge and workroom use the same tenant;
- the bridge's Exodus run appears in workroom context refs;
- synthetic boundary flags remain strict;
- bridge evidence and office artifact refs appear in the workroom;
- score, blocker, recommendation, and budget refs are present.

## Next integration step

After this bridge lands, Sociosphere should add a cross-repo integration report that links:

1. Exodus synthetic run fixture;
2. Prophet Workspace Exodus Migration Workroom bridge;
3. Sociosphere control-plane, disposition, and readiness state.

That report should be the durable proof that the v0 demo can be restarted and understood from repository state alone.
