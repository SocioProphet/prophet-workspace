# sherlock-scout (WO-D) — the thin vertical slice, end to end

Sherlock Scout v0: the grounded, governed, receipted answer that proves the Open Agent Continuum works
end to end (ADR-0001). It composes the three landed pieces:

```
question
  → WO-C workspace_ceiling  (meet over mounts; external clamped to Derived; what is reachable)
  → WO-A Graph.QueryCypher  (intent-routed 1–2 hop retrieval over mounted sources, safe subset)
  → AnswerCard              (answer · evidence · citations · freshness · confidence · missing-info · next-actions)
  → WO-B publish(f_!)       (hash-chained, replayable ProofArtifact — AC-1)
```

## Guarantees (all verified)

- **Grounded** answers cite graph edges and carry a confidence from composed TruthValue.
- **Ungrounded** answers never fabricate grounding — they hedge, set `missing_info`, and are **still
  receipted** (the answer contract is always honoured).
- **Intent routing:** a causal question narrows retrieval to `Causes` edges, a definitional one to `IsA`
  (the retrieval-planner idea; uses WO-A's `{relation:…}` filter).
- **Epistemic ceiling:** an external principal's answer is clamped to `Derived` (STAR-1); a
  Speculative-ceiling workspace clamps even a grounded answer. `admit_publish` is the backstop.
- **Reachability:** only sources on the mount table with `read`/`reference` are queried — nothing off the
  table is reachable. No readable mount ⇒ ungrounded ("no source mounted").

## Verify

`python3 tests/wo_d_test.py` → **17/17**: grounded (cites + replays), ungrounded (hedge + still
receipted), no-mount, external clamp, Speculative-ceiling clamp.

## Runtime follow-up (tracked)

Swap the in-memory fixture graph for the live HellGraph binding (WO-A runtime, #34); route publishes
through the shared `Ledger.Push` service (WO-B follow-up); surface the card in a Matrix room (WO-E,
`docs/ops` runbook). The semantics here are the contract those bindings must honour.
