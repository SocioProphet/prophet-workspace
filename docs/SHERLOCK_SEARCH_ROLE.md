# Sherlock Search Role

`sherlock-search` should not replace `lampstand` in the office/workspace program.

## Role split

### `SocioProphet/lampstand`

Lampstand is the canonical **local desktop indexing and search daemon**.

Use it for:
- local file crawling and reconciliation
- local metadata and text indexing
- inspectable health / stats on the Linux desktop
- desktop file discovery for SourceOS office workflows

### `SocioProphet/sherlock-search`

Sherlock Search should be the **higher-level search and discovery layer**.

Use it for:
- federated query planning across local, cloud, and memory sources
- result fusion and ranking across Lampstand, FogGraph, and memory retrieval
- product-level discovery semantics and relevance surfaces
- search UX logic that is broader than one local indexer

### `SocioProphet/memory-mesh`

Use it for:
- recall-before-query refinement
- memory-backed retrieval augmentation
- writeback-after-search and assistant flows where needed

### `SocioProphet/ontogenesis`

Use it for:
- vocabulary alignment and JSON-LD graph boundaries
- semantic unit typing and provenance-aware mapping
- cross-schema normalization between local files, cloud docs, tasks, comments, and workspace records

## Office/workspace stack implication

The effective search stack should be:

- Lampstand = local desktop source of truth for local office discovery
- FogGraph / platform indexing = cloud/workspace source of truth for cloud documents and workspace entities
- memory-mesh = recall layer
- ontogenesis = ontology/alignment layer
- Sherlock Search = cross-source search/discovery orchestration and ranking layer

## Rule

If the question is "find this file on my desktop" or "show me local office documents", Lampstand should be the primary backend.

If the question is "search my workspace across docs, tasks, chat, mail, and projects", Sherlock should orchestrate across Lampstand, platform indexes, and memory.
