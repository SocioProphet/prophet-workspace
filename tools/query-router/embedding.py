"""Pinned embedding space for the semantic router — the #602 discipline made a contract.

Noetica PR#600→#602 taught the estate a hard lesson (see the feedback memory
`embedding_space_pin_all_paths`): an embedding-space / dimension contract is only *real* if EVERY
place a vector is produced shares ONE space. #600 pinned the corpus to 768-dim but two query paths
still embedded the query in the sidecar's native 384-dim space; 384-query vs 768-corpus cosine
matched nothing → silent zero hits, red only where the native sidecar ran.

The semantic router therefore:
  * stores exemplar prompts as VECTORS in a single PinnedSpace (query-by-vector, never re-embed the
    exemplars from text at query time in a foreign space);
  * embeds the incoming query into that SAME PinnedSpace;
  * HARD-REJECTS a query vector whose dimension differs from the pinned space with a stable
    `embedding-space-mismatch` code — the exact 384-vs-768 failure, caught instead of silently
    cosine-missing.

Stdlib only (hashlib = SHA-256 / FIPS-180-4 algorithm, math). The FixtureEmbedder stands in for the
sovereign nomic embedder in conformance; a real embedder binds behind the identical PinnedSpace
contract.
"""
from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass


class EmbeddingSpaceMismatch(Exception):
    """A vector was produced in a different space than the pinned one (the #602 failure)."""

    code = "embedding-space-mismatch"

    def __init__(self, message: str):
        super().__init__(f"{self.code}: {message}")
        self.message = message


_TOKEN = re.compile(r"[a-z0-9][a-z0-9\-]*")


def _tokens(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


@dataclass(frozen=True)
class PinnedSpace:
    """One embedding space. `dims` is the authoritative dimension every vector MUST share."""

    dims: int

    def check(self, vec: list[float], *, where: str) -> None:
        """Raise unless `vec` lives in this space. Covers exemplar AND query embed paths (#602)."""
        if len(vec) != self.dims:
            raise EmbeddingSpaceMismatch(
                f"{where} vector has dim {len(vec)}, pinned space is {self.dims} "
                f"(a foreign-space vector would silently cosine-match nothing — #602)"
            )


class FixtureEmbedder:
    """Deterministic stdlib hashing embedder pinned to `space`.

    A signed hashing trick (token → bucket via SHA-256, sign via a second hash bit) gives a stable,
    dependency-free vector so the conformance suite is reproducible. The real embedder (nomic /
    sovereign embeddings) drops in behind the same `.space` + `.embed()` surface.
    """

    def __init__(self, space: PinnedSpace):
        self.space = space

    def embed(self, text: str) -> list[float]:
        vec = [0.0] * self.space.dims
        for tok in _tokens(text):
            h = int(hashlib.sha256(tok.encode("utf-8")).hexdigest(), 16)
            bucket = h % self.space.dims
            sign = 1.0 if (h >> 8) & 1 else -1.0
            vec[bucket] += sign
        return _l2_normalise(vec)


def _l2_normalise(vec: list[float]) -> list[float]:
    norm = math.sqrt(sum(v * v for v in vec))
    if norm == 0.0:
        return vec
    return [v / norm for v in vec]


def cosine(a: list[float], b: list[float]) -> float:
    """Cosine similarity. Both vectors are assumed already in the same PinnedSpace (checked upstream)."""
    if len(a) != len(b):
        raise EmbeddingSpaceMismatch(f"cosine of dim {len(a)} vs {len(b)}")
    return sum(x * y for x, y in zip(a, b))
