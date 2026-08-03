# knowledge-engineering — the estate's Knowledge/Dictionary-Engineering workbench (Watson-Knowledge-Studio equivalent)

- **Owner:** @mdheller
- **Status:** active
- **Last reviewed:** 2026-08-03

The sovereign, governed answer to **IBM Watson Knowledge Studio**. WKS is the human-in-the-loop loop
`documents → annotate → entity types → relation types → dictionaries → rules → versions → (rule-based +
ML model)`. This module ships that loop as a **contract with teeth** — and it is a **composition layer,
not a new model**: it BINDS the governed registries the estate already owns (consume-not-fork) and refuses
a workspace that tries to smuggle an ungoverned one back in.

```
documentSet → annotations (regis semantic-role #22/#27)
            → entityTypes + relationTypes  (REFERENCE regis entity-class #16 / semantic-role-kind #22 / ontogenesis OWL/SHACL)
            → dictionaries                 (BIND governed Systema Concept Entries — ontogenesis Platform/Systema)
            → rules → versions → modelRef  (rule-based + ML)
every promotion + every human authorship event = a receipt on the proof-artifact-spine
```

## What it consumes (nothing forked)

| Reference model half | Governed source it BINDS |
|---|---|
| Entity types | regis-entity-graph `entity-class` (#16, 25-member enum) + ontogenesis OWL/SHACL Domains |
| Relation / role types | regis-entity-graph `semantic-role-kind` (#22, 7-member enum) + span-alignment (#27) |
| Annotations (loop input) | regis `SemanticTokenTree` token roles (#22) — a token role is a candidate entity/relation/dictionary term |
| Dictionaries / terms | **Systema Concept Entry** (ontogenesis `Platform/Systema`): source-anchored, promotion-state-lifecycled, revisioned — a **learned/authored governed concept, never a static lookup list** |
| Receipts | `tools/proof-artifact-spine` (WO-B) `sha256:` ProofArtifact, and/or knowledge-state-lifecycle `urn:srcos:receipt:` |
| Evidence grades / zones | `tools/artifact-registry` (E1–E5), `tools/metadata-intake` (three-time) |

## The two doctrines it enforces

1. **Learn, don't match dictionaries** ([[feedback_learn_dont_match_dictionaries]]). A "dictionary" here is a
   GOVERNED, VERSIONED, LEARNED term set with provenance. A **static-match dictionary is REJECTED**: a
   `mode: static_match` lookup, an entry with **no `sourceAnchor`** (a bare word/tag), an entry whose
   provenance claims `learned` with **no learned predictor + evidence**, or an entry promoted past
   `reviewed_definition` on an **unreviewed** anchor (skipping the Systema lifecycle) — all rejected.
2. **The user is a first-class author.** add / overwrite / annotate / define are governed
   `AuthorshipEvent`s — **author-attributed + versioned + receipted** — that overwrite the learned layer by
   **supersession** (the prior `ConceptRevision` is retained, never deleted). Every artifact carries a
   `provenance.class ∈ {learned | human_authored | imported}`. A human override with **no author or no
   receipt is REJECTED**; `resolve_active()` returns the max-version active entry + its provenance class.

## What's here (spec-as-code)

| Path | Role |
|---|---|
| `schemas/ke-workspace.schema.json` | The `KnowledgeEngineeringWorkspace` descriptor (JSON Schema draft 2020-12; governance laws as structure). |
| `validate_ke_workspace.py` | Dependency-light validator: the cross-field teeth (KE-T1..T9) + a `validate_schema` drift-guard + `resolve_active()`. |
| `ke_receipts.py` | Consumes `proof-artifact-spine` to seal a KE promotion / authorship event as a hash-chained ProofArtifact. |
| `examples/*.valid.json` / `*.invalid.json` | 2 conforming workspaces (governed loop; human overwrite) + one negative fixture per tooth. |
| `tests/ke_test.py` | Conformance both ways + per-tooth mutation + `resolve_active` + a real receipt-spine seal/verify. |

## The teeth (enforced both ways)

- **KE-T1 learn-don't-match** — `mode` must be `governed`; every dictionary entry must have a
  `sourceAnchor`; `promotionState` must be a Systema lifecycle member; advancing past `reviewed_definition`
  needs a **reviewed** anchor; `implementation_linked`+ needs an `implementationSurface`. Static-match ⇒ REJECT.
- **KE-T2 governed-registry types** — every entity/relation binding names a known governed registry `$id`
  and a member in its enum. Unknown registry/member ⇒ REJECT.
- **KE-T3 rule integrity** — a rule's `entityTypeRefs`/`relationTypeRefs` must resolve to bindings in the
  workspace (so they resolve to the governed registry). Dangling ⇒ REJECT.
- **KE-T4 promotion receipt** — an annotation with `promotedTo` set must carry `promotionReceiptRef`.
- **KE-T5 authored supersession** — an `overwrite` must carry `supersedes` (prior retained). Authored with
  author + version + receipt + supersedes ⇒ VERIFIES + supersedes.
- **KE-T6 override needs author + receipt** — any `AuthorshipEvent` missing `author.id` or `receiptRef` ⇒ REJECT.
- **KE-T7 provenance + single-active** — every artifact carries `provenance.class` + a receipt; per
  `conceptRef` exactly one active version, and it is the max version.
- **KE-T8 receipt format** — every receipt is `sha256:<64hex>` (proof-artifact-spine) or
  `urn:srcos:receipt:...` (knowledge-state-lifecycle). SHA-256 = FIPS-180-4 algorithm.
- **KE-T9 doc types** — `docType` in the WKS-supported set; a text doc over 2000 words ⇒ REJECT (keep docs small).

## Verify

```
python3 tools/knowledge-engineering/validate_ke_workspace.py   # validates examples/; asserts *.invalid reject
python3 tools/knowledge-engineering/tests/ke_test.py           # both ways + per-tooth mutation + receipt seal/verify
```

## Runtime follow-up (tracked)

This is the **contract**. Wiring is the runtime half (epic #33): resolve `registryRef.member` against the
LIVE regis + ontogenesis SHACL/OWL gates (this module pins the regis enums, re-synced in CI); route
receipts through the shared `Ledger.Push`; and surface the loop in **client-vue** as the Knowledge-Studio
screen, integrated with the **Reasoning Chain Inspector** (annotations = KE input). Filed @mdheller.
