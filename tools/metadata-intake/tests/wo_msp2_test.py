"""MS-P2 conformance — `python3 tools/metadata-intake/tests/wo_msp2_test.py` (no pytest).

Teeth both ways: intake of real bytes yields a schema-conformant canonical record whose hashes match a
recompute over the same bytes and whose Intake CustodyEvent is chained + replayable; a non-conformant
intake (E3 with no null hypothesis; E5 with no counter-explanation) is refused BEFORE anything records.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

import blake3

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
TOOLS = os.path.dirname(PKG)
sys.path.insert(0, PKG)
sys.path.insert(0, os.path.join(TOOLS, "proof-artifact-spine"))

from intake import IntakeError, intake  # noqa: E402
from proof_artifact import dual_hash, verify_ledger  # noqa: E402
from publish import replay                 # noqa: E402

_passed = _failed = 0


def check(name, cond, detail=""):
    global _passed, _failed
    if cond:
        _passed += 1; print(f"  ok   {name}")
    else:
        _failed += 1; print(f"  FAIL {name} :: {detail}")


def base(**over):
    d = dict(corpus_id="SP-FORENSICS-2026", exhibit_id="AF-0042",
             original_filename="console-export.log", mime_type="text/plain",
             artifact_class="ConsolePaste", source_account="mdheller314@icloud.com",
             source_platform="LocalFilesystem", source_path_or_id="/Downloads/x.log",
             evidence_grade="E3", null_hypothesis_ids=["H0-benign"])
    d.update(over)
    return d


def main() -> int:
    content = b"The Baxter facility shut down after Hurricane Helene flooding in September 2024.\n"
    schema = json.loads((Path(PKG) / "schemas" / "metadata-record.schema.json").read_text())
    import jsonschema

    with tempfile.TemporaryDirectory() as d:
        led = Path(d) / "custody.jsonl"
        out = intake(content, ledger=led, **base())
        rec, receipt = out["record"], out["receipt"]

        # record conforms to the vendored standard schema
        errs = list(jsonschema.Draft202012Validator(schema).iter_errors(rec))
        check("record conforms to metadata-standards schema", not errs, str([e.message for e in errs][:2]))

        # hashes are the REAL hashes of the bytes (computed first, over raw content)
        check("blake3 matches recompute", rec["integrity"]["hash_blake3"] == blake3.blake3(content).hexdigest())
        check("sha256 matches recompute", rec["integrity"]["hash_sha256"] == hashlib.sha256(content).hexdigest())
        check("file_size_bytes exact", rec["identity"]["file_size_bytes"] == len(content))
        check("hash time is first (<= temporal times)",
              rec["integrity"]["hash_computed_at_micros"] <= rec["temporal"]["txn_created"])
        check("artifact_id assigned", len(rec["identity"]["artifact_id"]) >= 32)

        # Intake CustodyEvent chained + bound to the artifact hash + replayable
        check("Intake CustodyEvent emitted (seq 0, phase intake)",
              receipt["ledgerSeq"] == 0 and receipt["phase"] == "intake")
        check("custody event bound to the artifact hash",
              receipt["inputHash"] == dual_hash(rec["integrity"]["hash_blake3"]))
        ok, msg = verify_ledger(led); check("custody ledger verifies", ok, msg)
        check("intake run package replays", replay(receipt)["verified"])
        check("record travels in the receipt run package",
              receipt["runPackage"]["outputs"][0]["metadata_record"]["identity"]["exhibit_id"] == "AF-0042")

        # teeth: non-conformant intakes refused BEFORE recording
        try:
            intake(content, ledger=led, **base(evidence_grade="E3", null_hypothesis_ids=[]))
            check("E3 without null hypothesis refused", False, "intake accepted")
        except IntakeError as e:
            check("E3 without null hypothesis refused", e.code == "non-conformant", e.code)
        try:
            intake(content, ledger=led, **base(evidence_grade="E5", null_hypothesis_ids=["H0"], counter_explanations=[]))
            check("E5 without counter-explanation refused", False)
        except IntakeError as e:
            check("E5 without counter-explanation refused", e.code == "non-conformant", e.code)

        # a refused intake wrote nothing more (ledger still has only the 1 good event)
        ok2, _ = verify_ledger(led)
        n = sum(1 for _ in open(led))
        check("refused intakes recorded nothing (ledger still 1 event)", ok2 and n == 1, f"n={n}")

    print(f"\n{_passed} passed, {_failed} failed")
    return 1 if _failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
