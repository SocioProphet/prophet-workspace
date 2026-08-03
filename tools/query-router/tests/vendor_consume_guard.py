"""Consume-guard for the vendored `agentplane` fiber_retrieval closure — `python3 tests/vendor_consume_guard.py`.

The source-os#317 pattern. `selective_route.py` (WO-A2, #81) consumes the REAL fibered descend-abstain
gate; to run the cross-repo teeth in CI without `ESTATE_CHECKOUT_TOKEN` (#96) a pinned copy of that gate
+ its transitive closure is vendored under `vendor/agentplane/` and pinned by SHA-256 in
`vendor/VENDOR.md`.

This guard is the teeth that make the vendored copy a *pinned consume, not a fork*: it recomputes the
SHA-256 of every vendored file and FAILS CLOSED if any drifts from, is missing from, or is added beyond
the digests recorded in `VENDOR.md`. Fail-closed: an unparseable/empty manifest is itself a failure
(control that cannot fail — a guard that silently records nothing would be a guard that never fires).

Teeth both ways:
  POSITIVE — every recorded file exists and its recomputed digest equals the recorded one.
  NEGATIVE — a mutated / missing / extra vendored file (or an empty manifest) makes this exit non-zero.

Run:  python3 tests/vendor_consume_guard.py
"""
from __future__ import annotations

import hashlib
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)                       # tools/query-router
VENDOR = os.path.join(PKG, "vendor")
MANIFEST = os.path.join(VENDOR, "VENDOR.md")

# Rows in the VENDOR.md digest table:  | `agentplane/foo.py` | `<64 hex>` | ... |
_ROW = re.compile(r"^\|\s*`([^`]+\.py)`\s*\|\s*`([0-9a-fA-F]{64})`\s*\|")


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _recorded() -> dict[str, str]:
    """Parse the recorded {relpath: sha256} from the VENDOR.md digest table (the single authority)."""
    out: dict[str, str] = {}
    with open(MANIFEST, encoding="utf-8") as fh:
        for line in fh:
            m = _ROW.match(line)
            if m:
                out[m.group(1)] = m.group(2).lower()
    return out


def _vendored_py() -> set[str]:
    """Every `*.py` actually present under vendor/ (relative to vendor/), to catch ADDED files."""
    found: set[str] = set()
    for root, _dirs, files in os.walk(VENDOR):
        for name in files:
            if name.endswith(".py"):
                found.add(os.path.relpath(os.path.join(root, name), VENDOR))
    return found


def main() -> int:
    failed = 0

    if not os.path.isfile(MANIFEST):
        print(f"  FAIL vendor manifest missing :: {MANIFEST}")
        return 1

    recorded = _recorded()
    # Fail-closed: an empty/unparseable manifest is a failure, not a pass (a guard that guards nothing).
    if not recorded:
        print("  FAIL no digests parsed from VENDOR.md — the guard would guard nothing (fail-closed)")
        return 1

    print(f"consume-guard: {len(recorded)} vendored file(s) pinned in VENDOR.md")

    # POSITIVE + drift: each recorded file exists and matches its recorded digest.
    for rel, want in sorted(recorded.items()):
        path = os.path.join(VENDOR, rel)
        if not os.path.isfile(path):
            failed += 1
            print(f"  FAIL {rel} :: recorded in VENDOR.md but MISSING from vendor/ (drift)")
            continue
        got = _sha256(path)
        if got == want:
            print(f"  ok   {rel}  {got[:12]}…")
        else:
            failed += 1
            print(f"  FAIL {rel} :: DRIFT\n         recorded {want}\n         actual   {got}")

    # drift the other way: a `.py` present under vendor/ that is NOT pinned in VENDOR.md.
    extra = _vendored_py() - set(recorded)
    for rel in sorted(extra):
        failed += 1
        print(f"  FAIL {rel} :: present under vendor/ but NOT recorded in VENDOR.md (unpinned drift)")

    if failed:
        print(f"\nCONSUME-GUARD FAILED: {failed} drift(s). The vendored agentplane copy diverged from "
              "its pin.\nRe-vendor from the recorded commit or bump VENDOR.md deliberately "
              "(see vendor/VENDOR.md).")
        return 1
    print("\nconsume-guard OK: vendored agentplane copy matches its recorded SHA-256 pin (no drift).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
