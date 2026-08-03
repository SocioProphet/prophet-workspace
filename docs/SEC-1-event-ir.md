# SEC-1 — Event-IR (Agentic SecOps Immune System, observe layer)

Event-IR is the **normalized, typed sensor event** at the base of the immune system's
V1–V7 pipeline (Observe → … → Promote). A collector lowers a raw signal into one
Event-IR record; downstream, Event-IRs are the feedstock that ProofArtifact claims are
built from and hash-committed to (`tools/proof-artifact-spine`, WO-B).

Most of the SecOps framework is already built — ProofArtifact (hash-chained, fail-closed
AC-1, FIPS SHA-256), CustodyEvent (`custody_event.py`, 14 types), the WNZL zones, and the
23-topic taxonomy. Event-IR was the missing **observe-layer contract**; SEC-1 supplies it.
(Eval: prophet-workspace#62.)

## Placement (decision)

Event-IR lives in **`prophet-workspace/schemas` + `tools`**, co-located with the
proof-artifact spine, rather than in `source-os/schemas` or `workstation-contracts`:

- Event-IR must encode **byte-identically under the spine's `canonical()`** so an event
  can be hash-committed into a ProofArtifact. Co-location lets the validator *import* the
  spine encoder (single source of truth) instead of re-implementing it and risking drift.
- `prophet-workspace/schemas` already hosts the workspace contracts, and `tools/` already
  hosts their dependency-light validators (`validate_sp_file_naming.py` is the exact
  template — schema/validator lockstep, `additionalProperties:false`, good + invalid
  fixtures). SEC-1 matches that house style verbatim.
- SEC-2 (witness quorum) extends the same spine in the same repo, so both net-new pieces
  ship in one worktree / one PR that references #62 cohesively.
- `source-os` is a Nix/OS-image repo with no `schemas/` dir or validator convention; SEC-1
  would be orphaned there. `workstation-contracts` is the seam registry — the Tree-sitter
  lowering *seam* is registered there in spirit, but the encoder-reuse constraint keeps the
  schema itself next to the spine.

## Record shape

| Field | Meaning |
|---|---|
| `schema_version` | Contract version, `^1\.[0-9]+$`. MAJOR bump = breaking shape change. |
| `event_id` | Stable id; recommended content-address `sha256:<64hex>` of the canonical encoding minus `event_id`. |
| `time` | RFC3339/ISO-8601 UTC observation time. |
| `kind` | Normalized kind (open enum): `NET_TLS_HANDSHAKE`, `FILE_WRITE`, `POLICY_CHANGE`, `BOOT_ATTEST`, `EDITOR_LSP_MSG`, `SOURCE_EDIT`, … |
| `subject.scope` | Governed extent observed within. |
| `subject.labels.surface` | Host surface `H1..H7`. |
| `subject.labels.topic` | Governance-lane topic `LDA_01..LDA_23` (23-topic taxonomy). |
| `facts` | Kind-specific payload (open object at v1; see seam below). |
| `provenance.collector` / `.toolchain` | Which sensor + which toolchain/version produced it. |
| `provenance.inputs[]` | Content-addressed refs to raw upstream artifacts (may be empty, never absent). |
| `provenance.privacy.tier` | `local_only` \| `proof_only` \| `share_aggregate`. |

## Guarantees (enforced by `tools/validate_sec_event_ir.py`, teeth both ways)

- **Versioned**, **explicit provenance** (all four sub-fields required), **privacy-labelled**.
- Strict shape at every level (`additionalProperties:false`).
- **Deterministic canonical encoding**, key-order-independent, byte-identical to the spine's
  `canonical()` — the record can be hashed into a ProofArtifact without ambiguity.
- Schema and validator kept in **lockstep** (the validator exercises the schema, not just the data).

Rejected fixtures: bad privacy tier, missing provenance, out-of-range surface (`H8`),
out-of-range topic (`LDA_24`), unknown extra field.

## Seam: Tree-sitter → Event-IR lowering (documented, not built)

The **source-observe** collector lowers editor/source signals into Event-IR:

```
raw source buffer / LSP notification
   └─(Tree-sitter parse → concrete syntax tree)
        └─(lowering rules: node kind → Event-IR kind + facts)
             └─ Event-IR record  { kind: SOURCE_EDIT | EDITOR_LSP_MSG, subject.labels{surface,topic}, facts{...}, provenance{collector: "tree-sitter-lower", ...} }
```

This is a **documented seam**, deliberately *not* implemented in SEC-1 (the full parser is
out of scope). The contract fixes the seam's **output shape** so the lowering can be built
against a stable target:

- `kind` ∈ {`SOURCE_EDIT`, `EDITOR_LSP_MSG`}.
- `facts` per-kind schemas are the seam's remaining work (e.g. `SOURCE_EDIT.facts` =
  `{uri, node_kind, byte_range, symbol?}`); v1 leaves `facts` an open object so the lowering
  can iterate without a contract bump. Freezing per-kind `facts` schemas = a MINOR version.
- `provenance.toolchain` carries the concrete grammar+version (e.g. `tree-sitter-python@0.21`).

Tracked as a blocker issue (assigned @mdheller) for the lowering implementation + per-kind
`facts` schemas.
