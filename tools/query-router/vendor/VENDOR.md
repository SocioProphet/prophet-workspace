# Vendored dependency — `agentplane` fibered descend-abstain (`fiber_retrieval`)

**Consume-not-fork.** `selective_route.py` (WO-A2, #81) drives its graph→vector fall on the REAL
fibered `descend`-abstain conformal gate that lives in the sibling **`agentplane`** repo. That gate is
`tools/fiber_retrieval.py` plus its transitive sibling closure. To run the full cross-repo teeth in CI
**without a cross-repo checkout and without `ESTATE_CHECKOUT_TOKEN`** (#96), a **pinned copy** of that
closure is vendored here under `agentplane/`, guarded by a SHA-256 **consume-guard**
(`tools/query-router/tests/vendor_consume_guard.py`, the source-os#317 pattern): the guard recomputes
the digest of every vendored file and **fails closed** if it drifts from the digest recorded below.

This is a pinned *consume*, not a fork: the copy is never edited in place. When `agentplane` moves the
gate forward, re-vendor (copy the new blobs, bump the commit + digests below) — the guard makes silent
drift impossible. A live `agentplane` checkout still wins at runtime via `$AGENTPLANE_TOOLS`
(`selective_route._resolve_fiber_retrieval` prefers it; the vendored copy is the fallback).

## Source

| | |
|---|---|
| Source repo | `SocioProphet/agentplane` |
| Pinned commit | `97c3ea666dfae06eee91bf89b66f32f32063cede` (`origin/main` tip at vendor time) |
| Vendored on | 2026-08-03 |
| License | MIT (see `agentplane/LICENSE`) — compatible with the estate's MIT/Apache-only rule |
| Path in source | `tools/*.py` |

## Transitive closure

`fiber_retrieval.py` imports `conformal_gate`, `fiber_projection`, `stopgate_artifact`;
`stopgate_artifact` imports `ed25519_pure`. All five are pure-stdlib (no third-party deps), so the
vendored closure imports offline. The files retain their upstream layout under `agentplane/` so their
sibling imports (`import conformal_gate`, …) resolve unchanged.

## Recorded digests (SHA-256, FIPS-180-4) — the consume-guard authority

The guard parses this exact table. Each row is `` `path` `` → `` `sha256` `` relative to this
`vendor/` directory. Last-touch commit is the upstream commit that last modified that file.

| File | SHA-256 | Upstream last-touch |
|---|---|---|
| `agentplane/fiber_retrieval.py` | `7dbef85d5765780f40ccd0823c464a4bdca3186143c7dc10d4aff6cd9c65764c` | `4eba78f` |
| `agentplane/conformal_gate.py` | `2bb77d329d399be324d8e924fec3506cf065a69e3d1ea21c06b55742195c601f` | `a49bf16` |
| `agentplane/fiber_projection.py` | `13e0e0b565b8cfc311f7b471031429ddafce2604f04b750a2f3d7eea3904d935` | `9169fbd` |
| `agentplane/stopgate_artifact.py` | `3f8e845d2f725e336b1d9a492b01162fde250c9b878e13f1ca92f1876d2b1909` | `501fc4c` |
| `agentplane/ed25519_pure.py` | `b01b2265492b614f68fc9059c4128dd43bf33bb0a4d1624c7c8364a8debefa05` | `501fc4c` |

## Re-vendor procedure

```sh
SRC=~/dev/agentplane/tools           # a clean agentplane checkout at the new pin
DST=tools/query-router/vendor/agentplane
for f in fiber_retrieval conformal_gate fiber_projection stopgate_artifact ed25519_pure; do
  cp "$SRC/$f.py" "$DST/$f.py"
done
cp ~/dev/agentplane/LICENSE "$DST/LICENSE"
shasum -a 256 "$DST"/*.py           # paste the new digests into the table above + bump the pin
python3 tools/query-router/tests/vendor_consume_guard.py   # must pass after the bump
```
