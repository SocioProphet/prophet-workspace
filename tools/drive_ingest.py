#!/usr/bin/env python3
"""drive_ingest — ingest a local tree into the sovereign Drive blob store, with a manifest.

This is the Drive product's ingest path, exercised on real data. What distinguishes it
from `gcloud storage rsync` into a bucket is the MANIFEST: every ingested collection
gets a canonical-JSON, SHA-256-sealed record of what was ingested, so the Drive surface
can show provenance and a verifier can prove the remote copy matches what left the disk.

Three phases, deliberately separate, because the ordering is the whole safety property:

    plan     enumerate + hash locally; write the manifest; touch nothing remote
    push     rsync to the blob store; re-verify remote listing against the manifest
    reap     delete locally — ONLY for files the manifest says are verified present

`reap` refuses to run unless a verified manifest exists for the collection. Deleting
before verifying is the one mistake that cannot be undone, so it is not reachable by
a flag ordering accident: the verification result is persisted, and reap reads it.

Layout (canonical, established here):

    gs://<bucket>/drive/<seat>/<collection>/<relative-path>
    gs://<bucket>/drive/<seat>/<collection>/_manifest.json

`_manifest.json` carries per-file size + sha256, the collection digest (canonical-JSON
SHA-256 over the file table, matching the estate's SEAM-C `ledgerHash` convention), and
the provenance grade — `document-only` per the SourceLocator taxonomy, since an archived
blob identifies its source but carries no position within it.

Usage:
    drive_ingest.py plan  --root ~/Downloads/MIT --seat mdheller --collection downloads/MIT
    drive_ingest.py push  --collection downloads/MIT
    drive_ingest.py verify --collection downloads/MIT
    drive_ingest.py reap  --collection downloads/MIT      # requires verified manifest
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any

BUCKET = os.environ.get("PROPHET_DRIVE_BUCKET", "prophet-blobs-socioprophet-platform")
STATE = Path.home() / ".prophet" / "drive-ingest"
CHUNK = 1024 * 1024

# ── chain of custody, on the estate's EXISTING contracts ─────────────────────────
# An earlier revision invented a bespoke `verified: true` boolean. It should not have:
# ~/dev/exodus already defines CustodyEvent and VerificationResult for exactly this — moving
# data between zones with an auditable custody trail — and reusing them means the Drive
# product's provenance is queryable by the same tooling as every other migration, instead of
# being a private format only this script understands.
#
#   https://schemas.socioprophet.ai/exodus/custody-event.v0.1.json
#   exodus/schemas/verification-result.v1.json
#
# The phase → event mapping, and why each zone:
#
#   plan    Intake         null       → Discovery   PendingVerification
#   push    ZonePromotion  Discovery  → Landing     PendingVerification
#   verify  HashVerification / IntegrityViolation   Intact | Gap | IntegrityViolation
#   reap    Retirement     Landing    → Governed    Intact   (the local copy is retired;
#                                                             the bucket becomes authoritative)
#
# custody_status is what gates reap. Not a boolean this script chose the meaning of: a
# schema-validated enum whose values are defined elsewhere and mean the same thing estate-wide.
EXODUS_NS = uuid.UUID("6ba7b811-9dad-11d1-80b4-00c04fd430c8")   # RFC-4122 name-based namespace
CUSTODY_SCHEMA = Path.home() / "dev" / "exodus" / "schemas" / "custody-event.json"


def _stable_uuid(*parts: str) -> str:
    """Deterministic ids, so re-running a phase does not fabricate a new artifact identity.
    A random artifact_id per run would make the custody chain unjoinable, which is the one
    thing a custody chain must not be."""
    return str(uuid.uuid5(EXODUS_NS, "|".join(parts)))


def custody_log(collection: str) -> Path:
    return STATE / (collection.replace("/", "__") + ".custody.jsonl")


def emit_custody(
    collection: str, event_type: str, custody_status: str,
    zone_from: str | None, zone_to: str | None, digest: str | None = None, note: str | None = None,
) -> dict[str, Any]:
    """Append a CustodyEvent. Validated against the exodus schema when jsonschema and the
    schema file are both available — emitting an event that would fail the contract is the
    same defect as a receipt asserting its own verdict, so it fails loudly here rather than
    producing a trail nothing can read."""
    ev: dict[str, Any] = {
        "event_id": _stable_uuid(collection, event_type, str(time.time_ns())),
        "artifact_id": _stable_uuid("drive-collection", collection),
        "event_type": event_type,
        "actor_id": "prophet-workspace/tools/drive_ingest.py",
        "actor_type": "VerificationProcess" if event_type == "HashVerification" else "ExportProcess",
        "timestamp_micros": time.time_ns() // 1000,
        "zone_from": zone_from,
        "zone_to": zone_to,
        "tool_name": "drive_ingest",
        # hex_32 is 64 hex chars — bare, WITHOUT the sha256: prefix this script uses elsewhere.
        "hash_at_event": digest.split(":", 1)[-1] if digest else None,
        "custody_status": custody_status,
    }
    if note:
        ev["note"] = note
    _validate_custody(ev)
    STATE.mkdir(parents=True, exist_ok=True)
    with custody_log(collection).open("a") as f:
        f.write(json.dumps(ev) + "\n")
    return ev


def _validate_custody(ev: dict[str, Any]) -> None:
    if not CUSTODY_SCHEMA.exists():
        return                                  # exodus not checked out; nothing to validate against
    try:
        from jsonschema import Draft202012Validator
    except ImportError:
        return
    errs = list(Draft202012Validator(json.loads(CUSTODY_SCHEMA.read_text())).iter_errors(ev))
    if errs:
        sys.exit(f"refusing to emit a CustodyEvent that violates its contract: {errs[0].message}")


def custody_status(collection: str) -> str:
    """The CURRENT custody status: the last event's, or Gap if there is no trail at all.
    Gap rather than PendingVerification for an absent trail — 'no record' is a break in
    custody, not a pending step."""
    log = custody_log(collection)
    if not log.exists():
        return "Gap"
    lines = [l for l in log.read_text().splitlines() if l.strip()]
    return json.loads(lines[-1])["custody_status"] if lines else "Gap"


def canonical_json(obj: Any) -> str:
    """Canonical JSON — recursive key sort. Same convention as the estate's ledgerHash
    (agent-machine/lib/verb-sort.ts SEAM-C), so digests are comparable across tools."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def seal(obj: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(obj).encode()).hexdigest()


def file_sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        while chunk := f.read(CHUNK):
            h.update(chunk)
    return "sha256:" + h.hexdigest()


def manifest_path(collection: str) -> Path:
    return STATE / (collection.replace("/", "__") + ".json")


def load_manifest(collection: str) -> dict[str, Any]:
    p = manifest_path(collection)
    if not p.exists():
        sys.exit(f"no manifest for '{collection}' — run `plan` first ({p})")
    return json.loads(p.read_text())


# ── plan ──────────────────────────────────────────────────────────────────────
def cmd_plan(args: argparse.Namespace) -> int:
    root = Path(args.root).expanduser().resolve()
    if not root.is_dir():
        sys.exit(f"not a directory: {root}")

    files: list[dict[str, Any]] = []
    total = 0
    skipped: list[str] = []
    for p in sorted(root.rglob("*")):
        if not p.is_file() or p.is_symlink():
            if p.is_symlink():
                skipped.append(str(p.relative_to(root)))
            continue
        try:
            size = p.stat().st_size
            files.append({"path": str(p.relative_to(root)), "size": size, "sha256": file_sha256(p)})
            total += size
        except (OSError, PermissionError) as e:
            skipped.append(f"{p.relative_to(root)} ({e.__class__.__name__})")

    table = {"files": files}
    man = {
        "artifact": "drive-collection-manifest",
        "specVersion": "0.1.0",
        "seat": args.seat,
        "collection": args.collection,
        "sourceRoot": str(root),
        "bucket": BUCKET,
        "prefix": f"drive/{args.seat}/{args.collection}",
        "fileCount": len(files),
        "totalBytes": total,
        # SourceLocator taxonomy: an archived blob identifies its source but carries no
        # position within it. Recording the grade prevents a document-only locator being
        # mistaken later for a located one.
        "provenanceVersion": "document-only",
        "collectionDigest": seal(table),
        # The file table MUST be persisted, not merely sealed. An earlier revision stored
        # only collectionDigest — a digest of a table the manifest did not contain, so
        # `verify` had nothing to compare against and no verification was possible. That
        # is the estate's own "declared but unenforced" defect in miniature: a governance
        # field present in the record and readable by nothing.
        "files": files,
        "skipped": skipped,
        "verified": False,
        "verifiedAt": None,
    }
    STATE.mkdir(parents=True, exist_ok=True)
    manifest_path(args.collection).write_text(json.dumps(man, indent=2) + "\n")

    print(f"  planned  {args.collection}")
    print(f"    files   {len(files):,}")
    print(f"    bytes   {total:,} ({total/1024**3:.2f} GiB)")
    print(f"    digest  {man['collectionDigest']}")
    if skipped:
        print(f"    skipped {len(skipped)} (symlinks/unreadable) — not ingested, not reaped")
    emit_custody(args.collection, "Intake", "PendingVerification", None, "Discovery",
                 digest=man["collectionDigest"], note=f"{len(files)} files, {total} bytes enumerated and hashed locally")
    print(f"    → {manifest_path(args.collection)}")
    print(f"    custody: Intake → Discovery (PendingVerification)")
    return 0


# ── push ──────────────────────────────────────────────────────────────────────
def cmd_push(args: argparse.Namespace) -> int:
    man = load_manifest(args.collection)
    dest = f"gs://{man['bucket']}/{man['prefix']}"
    print(f"  pushing {man['fileCount']:,} files → {dest}")
    r = subprocess.run(
        ["gcloud", "storage", "rsync", "--recursive", man["sourceRoot"], dest],
        capture_output=False,
    )
    if r.returncode != 0:
        return r.returncode
    # Upload the manifest alongside the data so the collection is self-describing remotely.
    subprocess.run(
        ["gcloud", "storage", "cp", str(manifest_path(args.collection)), f"{dest}/_manifest.json"],
        capture_output=True,
    )
    emit_custody(args.collection, "ZonePromotion", "PendingVerification", "Discovery", "Landing",
                 digest=man["collectionDigest"], note=f"pushed to {dest}")
    print("  pushed. custody: Discovery → Landing (PendingVerification)")
    print("  run `verify` before `reap`.")
    return 0


# ── verify ────────────────────────────────────────────────────────────────────
def cmd_verify(args: argparse.Namespace) -> int:
    man = load_manifest(args.collection)
    dest = f"gs://{man['bucket']}/{man['prefix']}"
    r = subprocess.run(
        ["gcloud", "storage", "ls", "--recursive", dest], capture_output=True, text=True
    )
    if r.returncode != 0:
        sys.exit(f"remote listing failed:\n{r.stderr}")

    remote = {
        line.strip()[len(dest) + 1 :]
        for line in r.stdout.splitlines()
        if line.strip().startswith(dest) and not line.strip().endswith("/")
    }
    remote.discard("_manifest.json")
    local = {f["path"] for f in man["files"]}

    missing = sorted(local - remote)
    extra = sorted(remote - local)

    print(f"  verify {args.collection}")
    print(f"    local  {len(local):,}")
    print(f"    remote {len(remote):,}")
    if missing:
        print(f"    ❌ MISSING REMOTELY: {len(missing)} — reap refused")
        for m in missing[:10]:
            print(f"       {m}")
        man["verified"] = False
        manifest_path(args.collection).write_text(json.dumps(man, indent=2) + "\n")
        emit_custody(args.collection, "HashVerification", "Gap", "Landing", "Landing",
                     note=f"{len(missing)} of {len(local)} objects absent remotely")
        print("    custody: Gap — reap refused")
        return 1
    if extra:
        print(f"    ⚠️  {len(extra)} extra objects remote (pre-existing?) — not blocking")

    # Spot-check content, not just presence: a listing proves a name exists, not that the
    # bytes match. Re-hash a sample of remote objects against the manifest.
    sample = man["files"][:: max(1, len(man["files"]) // 8)][:8]
    bad: list[str] = []
    for f in sample:
        got = subprocess.run(
            ["gcloud", "storage", "cat", f"{dest}/{f['path']}"], capture_output=True
        )
        if got.returncode != 0:
            bad.append(f"{f['path']} (unreadable)")
            continue
        h = "sha256:" + hashlib.sha256(got.stdout).hexdigest()
        if h != f["sha256"]:
            bad.append(f"{f['path']} (hash mismatch)")
    if bad:
        print(f"    ❌ CONTENT MISMATCH on {len(bad)}/{len(sample)} sampled — reap refused")
        for b in bad:
            print(f"       {b}")
        man["verified"] = False
        manifest_path(args.collection).write_text(json.dumps(man, indent=2) + "\n")
        # IntegrityViolation is both an event_type and a custody_status in the contract, and
        # both apply: bytes that do not match are a stronger failure than bytes that are absent.
        emit_custody(args.collection, "IntegrityViolation", "IntegrityViolation", "Landing", "Landing",
                     note=f"{len(bad)} of {len(sample)} sampled objects failed content hash")
        print("    custody: IntegrityViolation — reap refused")
        return 1

    print(f"    ✅ all present; {len(sample)}/{len(sample)} sampled hashes match")
    man["verified"] = True
    man["verifiedAt"] = subprocess.run(
        ["date", "-u", "+%Y-%m-%dT%H:%M:%SZ"], capture_output=True, text=True
    ).stdout.strip()
    manifest_path(args.collection).write_text(json.dumps(man, indent=2) + "\n")

    emit_custody(args.collection, "HashVerification", "Intact", "Landing", "Landing",
                 digest=man["collectionDigest"],
                 note=f"{len(local)} objects present; {len(sample)} sampled content hashes matched")
    # VerificationResult, on the estate's existing contract, so the claim is machine-readable
    # rather than a line of console output nobody can query later.
    (STATE / (args.collection.replace("/", "__") + ".verification.json")).write_text(json.dumps({
        "verification_id": _stable_uuid("verify", args.collection, man["collectionDigest"]),
        "claim": f"every file in collection '{args.collection}' is present in {dest} with matching content",
        "evidence_artifact_refs": [man["collectionDigest"]],
        "verification_method": (
            "full remote listing compared against the sealed manifest file table (presence), plus "
            f"re-hashing {len(sample)} sampled objects fetched from the bucket (content)"
        ),
        "verified_by": "prophet-workspace/tools/drive_ingest.py",
        "verified_at": man["verifiedAt"],
        # Presence is exhaustive; content is sampled. Saying "high" rather than "certain" is the
        # honest reading, and the method field states exactly which part was sampled.
        "confidence": "high",
        "reproducible": True,
        "notes": f"{len(extra)} extra objects present remotely and not reaped" if extra else None,
    }, indent=2) + "\n")
    print("    custody: Intact — reap permitted")
    return 0


# ── reap ──────────────────────────────────────────────────────────────────────
def cmd_reap(args: argparse.Namespace) -> int:
    man = load_manifest(args.collection)
    # Gated on the CUSTODY STATUS, not on a boolean this script invented the meaning of.
    # `Intact` is defined by exodus/schemas/custody-event.json and means the same thing
    # everywhere in the estate; a bespoke `verified: true` meant only what this file said it did.
    status = custody_status(args.collection)
    if status != "Intact":
        sys.exit(
            f"refusing to reap '{args.collection}': custody status is {status}, not Intact.\n"
            f"run `verify` first. Deleting before verifying is the one unrecoverable mistake."
        )
    if not man.get("verified"):
        sys.exit(f"refusing to reap '{args.collection}': custody says Intact but the manifest "
                 f"is not marked verified — the two disagree, which is itself a reason to stop.")
    root = Path(man["sourceRoot"])
    freed = 0
    gone = 0
    for f in man["files"]:
        p = root / f["path"]
        if p.exists():
            freed += f["size"]
            p.unlink()
            gone += 1
    # Remove now-empty directories, deepest first. Never removes the root itself.
    for d in sorted((p for p in root.rglob("*") if p.is_dir()), key=lambda x: -len(x.parts)):
        try:
            d.rmdir()
        except OSError:
            pass
    emit_custody(args.collection, "Retirement", "Intact", "Landing", "Governed",
                 digest=man["collectionDigest"],
                 note=f"{gone} local files retired, {freed} bytes freed; bucket copy is now authoritative")
    print(f"  reaped {gone:,} files, freed {freed/1024**3:.2f} GiB from {root}")
    print(f"    custody: Landing → Governed (Retirement)")
    if man["skipped"]:
        print(f"    kept {len(man['skipped'])} skipped (never ingested)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("plan", help="enumerate + hash locally; write manifest")
    p.add_argument("--root", required=True)
    p.add_argument("--seat", required=True)
    p.add_argument("--collection", required=True)
    p.set_defaults(fn=cmd_plan)

    for name, fn, helptext in (
        ("push", cmd_push, "rsync to the blob store"),
        ("verify", cmd_verify, "check remote against manifest (presence + sampled hashes)"),
        ("reap", cmd_reap, "delete locally — requires a verified manifest"),
    ):
        q = sub.add_parser(name, help=helptext)
        q.add_argument("--collection", required=True)
        q.set_defaults(fn=fn)

    args = ap.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
