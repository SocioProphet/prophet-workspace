# graphrag-grounding — grounded answer with page reference (Knowledge Hub, pw#76)

The buildable, teeth-backed slice of the **Knowledge Hub + InnerSource intelligence** capability
(pw#76 item: *Knowledge Hub + InnerSource intel*). It is the contract for the last arrow of the
GraphRAG page-reference grounding loop (reference frame 5):

```
Query
  → Indexing   (Page Contents → vision → KG Indexings + Vector Embeddings)
  → Retrieval  (pages)
  → Generation
  → ANSWER WITH PAGE REFERENCE        ← this contract
metrics: Retrieval Page Accuracy · Question-Answer Similarity F1
```

An answer is only admissible if it carries **page/source references that resolve against the indexed
KG+vector store**, and only **VERIFIES** if the cited pages clear the retrieval-accuracy floor and the
answer clears the QA-similarity floor. Every answer — verified or rejected — is **receipted**.

## Consume-not-fork

This composes pieces already landed in this repo; it forks nothing:

| Consumed | From | Used for |
|---|---|---|
| **AnswerCard** shape (answer · grounded · citations · confidence · freshness · missing_info · next_actions · epistemic_level) | `tools/sherlock-scout/scout.py` | `GroundedAnswer` extends each citation with a resolvable `page_ref` |
| **Receipt spine** (`emit_proof_artifact`, `RunPackage`, `verify_ledger`, `sha256`, `canonical`) | `tools/proof-artifact-spine/` | every answer is a hash-chained, replayable ProofArtifact (AC-1) |
| **Evidence grades** E1..E5 (Speculative → Corroborated) | `metadata-standards` / `tools/metadata-intake` | annotation provenance grade |
| **HellGraph write shape** `addNode(id, labels, props)` + edges | `~/dev/hellgraph` (`ts/src/cypher.ts`, `store.ts`) | annotation → KG write plan (fixtures only; **no live write**) |

The **page anchor is the gap this fills**: sherlock-scout citations are graph-edge refs `{tail, path}`,
and prophet-platform's `graphrag.ts` / `KnowledgeNugget.sourceRef` carry triples / character spans but
no page anchor. `page_ref = {source_id, page, span?, quote?}` is the new, resolvable locator.

## The contract

`GroundedAnswer` = the scout AnswerCard, with each citation carrying
`page_ref = {source_id, page, span?, quote?}`. It grades against a `PageIndex` (which `(source_id,
page)` pairs the store actually indexed) and a `gold = {answer, pages[]}`.

### Teeth (fail-closed order, `grounding.grade_answer`)

An answer **VERIFIES** iff:
1. it carries ≥ 1 page reference — else **REJECTED** *(no page references)*;
2. every page reference **resolves** against the index — else **REJECTED** *(unresolvable page references)*;
3. `retrieval_page_accuracy(cited, gold) ≥ floor` (default 0.5) — else **REJECTED** *(below the accuracy floor)*;
4. `qa_similarity_f1(answer, gold_answer) ≥ qa_floor` (default 0.3) — else **REJECTED** *(below the QA floor)*.

### Metrics (`metrics.py`, computable & pure)

- **`retrieval_page_accuracy(cited_pages, gold_pages)`** — `|cited ∩ gold| / |cited|` over
  `(source_id, page)` pairs: precision of the cited page set. Empty ⇒ 0.0.
- **`qa_similarity_f1(pred, gold)`** — SQuAD-style token-level F1 (case/punct/article-normalized bag
  overlap → precision, recall, F1).

## Annotation → KG (`annotation_kg.py`)

An annotation (select text → **Highlight + Comment + Tags**) becomes a **provenance-sealed** KG write
plan: an `Annotation` node, a `Document` node, `Tag` nodes, and `ANNOTATES` / `TAGGED` edges — every
node shaped for HellGraph `addNode(id, labels, props)`. The seal is SHA-256 (FIPS 180-4 *algorithm*,
not a FIPS-140 module) over the canonical annotation core; editing the highlight changes the seal,
reordering tags does not. **Pure function — no live graph write.**

## Verify (teeth, both ways)

```bash
python3 tests/grounding_test.py     # 32 checks: metrics, verdicts, receipts+chain, annotation→KG
python3 validate_grounding.py       # fixture conformance: *.valid ⇒ VERIFY, *.invalid ⇒ REJECTED
```

Fixtures (`fixtures/`) include the reference case **"prove √2 is not rational → cite pages"**
(`sqrt2-irrationality.valid.json`, VERIFIES: rpa=1.0, f1≈0.81) and four negative fixtures that MUST be
rejected — no page-refs, unresolvable ref, below accuracy floor, below QA floor — each for its specific
reason. The filename convention is load-bearing: a `*.invalid.json` that VERIFIES fails the validator
(the guard cannot be silently disarmed).

## Runtime follow-up (tracked, out of scope here)

Bind `PageIndex` to the live HellGraph + vector store (the WO-A gateway / vendored `@socioprophet/hellgraph`
retrieval); route `emit_proof_artifact` through the shared `Ledger.Push` service; commit the annotation
write plan through a gated HellGraph write path. The semantics here are the contract those bindings must
honour.
