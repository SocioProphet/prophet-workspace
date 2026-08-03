# image-promotion-gate (WO-G)

The **SourceOS image validation promotion gate**. An image build may update Git / close its issue **only
if it passes this gate**. WO-G of [ADR-0001 — Open Agent Continuum](../../docs/adr/ADR-0001-open-agent-continuum.md),
implementing the SourceOS Linux Image Generation & Validation Corpus §"Promotion gate before Git update /
task closure".

## The law it enforces

Shipping an image is a `publish` (`f_!`) in the estate adjunction (ADR-0001 §3), so it obeys **AC-1, the
receipt law**: a promotion that cannot emit a receipt is **not** a promotion. The key identification (WO-G):

> **The EvidenceBundle IS a ProofArtifact.**

There is no second provenance store. The gate emits its promotion receipt onto the **same** hash-chained,
FIPS-approved (SHA-256) receipt spine every other `publish` uses — [`proof-artifact-spine`](../proof-artifact-spine)
— and its refusal onto the **same** spine as a 14-type `CustodyEvent`. One spine, both record types.

## Behaviour (fail-closed)

| Verdict | Action |
|---|---|
| **PASS** / **PASS-WITH-EXPLICIT-WAIVER** | emit a **ProofArtifact** (via the WO-B `publish`=`f_!` path) recording the promotion + a linked `ZonePromotion` custody event → return the receipt. Git may now update. |
| **FAIL** | emit a `PolicyException` **CustodyEvent** (reason codes in the note) and raise `PromotionRefused`. **No ProofArtifact is written; nothing is promoted; Git is NOT updated.** |

Fail-closed means: a required category whose evidence is **absent** is a FAIL exactly like one that
explicitly failed. A bundle missing any required category is refused — there is no "skip".

## Required categories (default policy)

`build_completed` · `provenance_manifest` (source_revision, package_manifest, policy_manifest, sbom,
config_digest) · `static_validation` · `dynamic_scenarios` (required scenarios pass) ·
`no_unapproved_policy_violations` · `evidence_bundle_complete` · `replay_ref` · `red_blue_smoke` ·
`approvals` (required approver roles present).

Extra corpus categories (CloudShell reachability, sensor/world-model refresh, retrieval freshness) are
supported by adding them to `GatePolicy.required_categories`; a required category with **no evaluator**
refuses (fail-closed), so they cannot be silently ignored.

A passing promotion publishes at epistemic level **Measured** — the MS-P6 grade ladder maps E4
Authenticated (hash verified, chain intact) → Measured, which is exactly a complete, replayable,
hash-bound bundle.

## Pieces

| File | Role |
|---|---|
| `promotion_gate.py` | `EvidenceBundle`, `GatePolicy`, `evaluate_gate()` (pure verdict), `promote()` (PASS→ProofArtifact+ZonePromotion / FAIL→PolicyException+`PromotionRefused`). |
| `tests/wo_g_test.py` | 25 checks, teeth both ways. Run: `python3 tools/image-promotion-gate/tests/wo_g_test.py` → 25/25. |

## Run

```bash
python3 -m pip install -r tools/proof-artifact-spine/requirements.txt   # blake3 (advisory dual-hash)
python3 tools/image-promotion-gate/tests/wo_g_test.py
```

## Where the inputs come from

The gate is repo-agnostic on inputs: it consumes an `EvidenceBundle` assembled from a SourceOS build —
`source-os` emits the build/provenance manifest (`.sourceos/manifest.json`, `scripts/sign-and-provenance.sh`),
static validation, and the `tests/agent-s` dynamic-scenario `result.json` files (each a scenario result).
The gate is the governance-plane decision that authorises `source-os`'s downstream `scripts/promote.sh`
(Katello dev→candidate→stable) and the Git update. It lives here, beside the receipt spine it reuses,
rather than in `source-os` (which is Nix-based and has no receipt tooling) so the spine is not forked.
