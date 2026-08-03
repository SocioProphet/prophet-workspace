"""SEC-2 — witness quorum signing for ProofArtifacts (the immune system's promotion rule).

A ProofArtifact (WO-B, `proof_artifact.py`) is a hash-chained, self-consistent claim. SEC-2
adds the *promotion* rule: a claim is only promotable when a **k-of-N witness quorum**
(default 2-of-N) has independently signed it. This module signs, assembles, verifies, and
gates promotion on that quorum, and emits the quorum block onto the ProofArtifact.

FIPS posture (mirrors how the spine made BLAKE3 advisory)
--------------------------------------------------------
The eval named FROST 2-of-N. **FROST / Schnorr threshold signatures over ed25519 are NOT
FIPS-approved**, and no FIPS-validated FROST implementation is available in Python (the only
crypto lib present is `cryptography`; no `frost`/`pynacl`). So SEC-2 does NOT use FROST.

Instead the quorum is realized as **independent per-witness FIPS ECDSA signatures over NIST
P-256 with SHA-256** (FIPS 186-4; P-256 + SHA-256 are 140-3 approvable), verified against a
**k-of-N policy**. This is a genuine multisig quorum (N distinct signatures, k required), not
an aggregated threshold signature — larger on the wire, but FIPS-clean and requiring no
trusted key-generation ceremony. This mirrors the estate's existing `quorum_proof.schema.json`
(independent signatures + a rule) rather than inventing a new primitive.

- FIPS-approved (this module): ECDSA P-256 / SHA-256 quorum. **This is the default.**
- Advisory / aspirational (NOT used): FROST-ed25519 aggregated threshold sig — smaller block,
  single verify — pending a FIPS-validated implementation. Tracked as a blocker issue.

The crypto here is real (via `cryptography`), not mocked.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import Prehashed  # noqa: F401  (kept explicit)

from proof_artifact import canonical, sha256

SCHEMA_VERSION = "1.0"
SCHEME = "ecdsa-p256-quorum"
ALG = "ECDSA_P256_SHA256"
DEFAULT_K = 2

FIPS_POSTURE = (
    "ecdsa-p256-quorum: independent per-witness ECDSA P-256 / SHA-256 signatures (FIPS 186-4; "
    "140-3 approvable) verified k-of-N. FROST/Schnorr-ed25519 is NOT FIPS-approved and is NOT "
    "used here; it is the advisory path pending a FIPS-validated implementation."
)


class QuorumError(Exception):
    pass


class PromotionDenied(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


@dataclass
class Witness:
    """An enrolled witness: id + its private key. Public roster entry via `roster_entry()`."""
    witness_id: str
    _private_key: ec.EllipticCurvePrivateKey

    @classmethod
    def generate(cls, witness_id: str) -> "Witness":
        return cls(witness_id, ec.generate_private_key(ec.SECP256R1()))

    def _public_spki_b64(self) -> str:
        der = self._private_key.public_key().public_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        return base64.b64encode(der).decode("ascii")

    def roster_entry(self) -> dict:
        return {"witness_id": self.witness_id, "alg": ALG, "public_key_spki_b64": self._public_spki_b64()}

    def sign(self, signed_payload: bytes) -> dict:
        sig = self._private_key.sign(signed_payload, ec.ECDSA(hashes.SHA256()))
        return {"witness_id": self.witness_id, "sig_b64": base64.b64encode(sig).decode("ascii")}


def _committed(receipt: dict) -> dict:
    entry_hash = receipt.get("entryHash")
    if not isinstance(entry_hash, str) or not entry_hash.startswith("sha256:"):
        raise QuorumError("receipt is missing a valid entryHash to witness")
    return {"record_type": "ProofArtifact", "entry_hash": entry_hash}


def _signed_payload(receipt: dict) -> bytes:
    """The exact bytes each witness signs: canonical(committed)."""
    return canonical(_committed(receipt)).encode("utf-8")


def build_quorum_block(receipt: dict, roster: list[Witness], signers: list[Witness], k: int = DEFAULT_K) -> dict:
    """Assemble a k-of-N witness quorum block for `receipt`.

    `roster` = all enrolled witnesses (defines N and the public keys). `signers` ⊆ `roster`
    are the witnesses that actually sign now. Assembling does NOT itself enforce k — that is
    the verifier/promotion gate's job (so an under-quorum block is representable and then
    correctly refused, which is what the teeth test)."""
    if not roster:
        raise QuorumError("roster must be non-empty")
    roster_ids = [w.witness_id for w in roster]
    if len(set(roster_ids)) != len(roster_ids):
        raise QuorumError("roster witness_ids must be unique")
    payload = _signed_payload(receipt)
    committed = _committed(receipt)
    return {
        "schema_version": SCHEMA_VERSION,
        "scheme": SCHEME,
        "threshold": {"k": k, "n": len(roster)},
        "committed": committed,
        "signed_payload_hash": sha256(canonical(committed)),
        "roster": [w.roster_entry() for w in roster],
        "signatures": [w.sign(payload) for w in signers],
        "fips_posture": FIPS_POSTURE,
    }


def verify_quorum(receipt: dict, block: dict) -> tuple[bool, str]:
    """Verify a quorum block against a ProofArtifact, fail-closed. Returns (ok, message).

    Checks: scheme; committed binds to this receipt's entryHash; signed_payload_hash matches;
    every signature is from a rostered witness and cryptographically valid over the payload;
    DISTINCT valid witnesses >= k; roster size == n. Any deviation => (False, reason)."""
    if block.get("scheme") != SCHEME:
        return False, f"unexpected scheme {block.get('scheme')!r}"

    try:
        expected_committed = _committed(receipt)
    except QuorumError as e:
        return False, str(e)
    if block.get("committed") != expected_committed:
        return False, "committed does not bind to this ProofArtifact's entryHash"

    if block.get("signed_payload_hash") != sha256(canonical(expected_committed)):
        return False, "signed_payload_hash does not match canonical(committed)"

    threshold = block.get("threshold") or {}
    k = threshold.get("k")
    n = threshold.get("n")
    roster = block.get("roster") or []
    if not isinstance(k, int) or not isinstance(n, int) or k < 1:
        return False, "invalid threshold"
    if len(roster) != n:
        return False, f"roster size {len(roster)} != declared n {n}"

    roster_ids = [r.get("witness_id") for r in roster]
    if len(set(roster_ids)) != len(roster_ids):
        return False, "duplicate witness_id in roster"

    keys: dict[str, ec.EllipticCurvePublicKey] = {}
    for r in roster:
        if r.get("alg") != ALG:
            return False, f"roster witness {r.get('witness_id')!r} has non-FIPS alg {r.get('alg')!r}"
        try:
            der = base64.b64decode(r["public_key_spki_b64"], validate=True)
            keys[r["witness_id"]] = serialization.load_der_public_key(der)
        except Exception as e:  # malformed key => fail closed
            return False, f"roster witness {r.get('witness_id')!r} has an unloadable public key ({e})"

    payload = _signed_payload(receipt)
    valid_witnesses: set[str] = set()
    for s in block.get("signatures", []):
        wid = s.get("witness_id")
        if wid not in keys:
            return False, f"signature from unrostered witness {wid!r} (fail-closed)"
        try:
            sig = base64.b64decode(s["sig_b64"], validate=True)
            keys[wid].verify(sig, payload, ec.ECDSA(hashes.SHA256()))
        except (InvalidSignature, Exception):
            return False, f"invalid signature from witness {wid!r}"
        valid_witnesses.add(wid)  # distinct: duplicate sigs from one witness count once

    if len(valid_witnesses) < k:
        return False, f"under quorum: {len(valid_witnesses)} valid distinct witness(es) < k={k}"

    return True, f"quorum satisfied ({len(valid_witnesses)}/{k} of {n})"


def attach_quorum(receipt: dict, block: dict) -> dict:
    """Emit the quorum signature block onto the ProofArtifact (returns a new dict).

    The block is attached under `witnessQuorum`. Note this is added AFTER the receipt's own
    entryHash is computed and is what the witnesses sign over — so attaching it does not
    invalidate the ledger chain (the chain hashes the pre-quorum body; the quorum binds back
    to that body's entryHash)."""
    out = dict(receipt)
    out["witnessQuorum"] = block
    return out


def promote(receipt: dict, block: dict, k: int | None = None) -> dict:
    """The promotion rule: a ProofArtifact is promotable ONLY if it carries a valid k-of-N
    witness quorum. Fail-closed — raises PromotionDenied otherwise. Returns the receipt with
    the quorum attached on success."""
    ok, msg = verify_quorum(receipt, block)
    if not ok:
        raise PromotionDenied("quorum-required", f"promotion refused — {msg}")
    if k is not None and block.get("threshold", {}).get("k") != k:
        raise PromotionDenied("quorum-policy", f"quorum k={block.get('threshold', {}).get('k')} != required k={k}")
    return attach_quorum(receipt, block)
