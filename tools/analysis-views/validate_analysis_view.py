#!/usr/bin/env python3
"""Validator for the Registered Analysis View descriptor (AV-1 of issue #60).

AV-1: LSA / LSI / LDA semantic spaces registered as GOVERNED, Noria-style materialized analysis views.
The descriptor fuses two halves that the estate keeps apart:
  - GENESYS Ring-Zero reproducibility (pinned seed + output/manifest hash, closed-space builders), and
  - the estate's governance (WNZL zone_path MS-P5, epistemic access WO-C, provenance WO-B).

Two layers, matching the metadata-standards house style:
  1. JSON Schema (schemas/analysis-view.schema.json) — shape, enums, required blocks.
  2. Cross-field "teeth" pure JSON Schema can't express, enforced BOTH ways (valid must pass; every
     negative fixture must fail):
       AV-T1 model<->params: LSA needs dim only; LSI needs rank only; LDA needs k only. A view carrying
             another model's basis param is a silent fork risk -> reject.
       AV-T2 reproducibility law: an output_hash REQUIRES a pinned deterministic reconstruction
             (reconstruction.deterministic && from_seed). A hash you cannot regenerate is not evidence.
       AV-T3 WNZL order: zone_path must be a strictly-ascending path in the canonical zone order (MS-P5).
       AV-T4 governed publication: a view owning Governed/Diamond REQUIRES signed + signer + manifest_hash
             (mirrors the zone-lifecycle Governed/Diamond gates).
       AV-T5 external clamp (AC-2 / STAR-1): origin=external ⇒ epistemic_ceiling <= Derived.
       AV-T6 emergence gate (GENESYS "fully fibered before expansion"): a transform.expansion REQUIRES
             coverage.ratio == 1.0 AND a stability block. No basis expansion over an uncovered atlas.
       AV-T7 lifecycle coherence: eviction != none needs a freshness window; deterministic reconstruction
             needs non-empty source_refs (cannot reconstruct from nothing).

Exit 0 = conforms; 1 = conformance failure; 2 = usage error. Validates one file or all examples/.
Run: `python3 tools/analysis-views/validate_analysis_view.py [descriptor.json ...]`
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SCHEMA = ROOT / "schemas" / "analysis-view.schema.json"

# Canonical vocabularies (authorities, inlined to keep the validator dependency-light & standalone):
#   WNZL zone order -> tools/zone-lifecycle (MS-P5);  epistemic levels -> tools/workspace-controller (WO-C).
ZONES = ["Discovery", "Landing", "Examination", "Integration", "Governed", "Diamond"]
_ZONE_RANK = {z: i for i, z in enumerate(ZONES)}
LEVELS = ["Speculative", "Derived", "Measured", "Proved"]
_LEVEL_RANK = {lv: i for i, lv in enumerate(LEVELS)}
EXTERNAL_CEILING = "Derived"                       # STAR-1 / AC-2
GOVERNED_RANK = _ZONE_RANK["Governed"]
_MODEL_PARAM = {"LSA": "dim", "LSI": "rank", "LDA": "k"}


def _cross_field(rec: dict) -> list[str]:
    errs: list[str] = []
    model = rec.get("model", {}).get("kind")
    tr = rec.get("transform", {})
    integ = rec.get("integrity", {})
    life = rec.get("lifecycle", {})
    gov = rec.get("governance", {})

    # AV-T1 model <-> params
    if model in _MODEL_PARAM:
        want = _MODEL_PARAM[model]
        if want not in tr:
            errs.append(f"AV-T1 model/params: model {model} requires transform.{want}")
        for other_model, other_param in _MODEL_PARAM.items():
            if other_param != want and other_param in tr:
                errs.append(f"AV-T1 model/params: model {model} must NOT carry {other_param} (belongs to {other_model})")

    # AV-T2 reproducibility: an output_hash requires a pinned, deterministic reconstruction
    if integ.get("output_hash"):
        rec_blk = life.get("reconstruction", {})
        if not (rec_blk.get("deterministic") and rec_blk.get("from_seed")):
            errs.append("AV-T2 reproducibility: output_hash requires reconstruction.deterministic && from_seed")

    # AV-T3 WNZL zone_path strictly ascending in canonical order
    zp = gov.get("zone_path", [])
    if zp:
        ranks = [_ZONE_RANK[z] for z in zp if z in _ZONE_RANK]
        if len(ranks) != len(zp) or any(ranks[i] >= ranks[i + 1] for i in range(len(ranks) - 1)):
            errs.append(f"AV-T3 WNZL: zone_path {zp} must be strictly ascending in {ZONES}")
    top_rank = max((_ZONE_RANK[z] for z in zp if z in _ZONE_RANK), default=-1)

    # AV-T4 governed/diamond publication requires signature + manifest
    if top_rank >= GOVERNED_RANK:
        if not integ.get("signed"):
            errs.append("AV-T4 governed: a view owning Governed/Diamond requires integrity.signed")
        if not integ.get("manifest_hash"):
            errs.append("AV-T4 governed: a view owning Governed/Diamond requires integrity.manifest_hash")
        if not gov.get("provenance", {}).get("signer"):
            errs.append("AV-T4 governed: a view owning Governed/Diamond requires provenance.signer")

    # AV-T5 external clamp
    prov = gov.get("provenance", {})
    ceil = gov.get("access", {}).get("epistemic_ceiling")
    if prov.get("origin") == "external" and ceil in _LEVEL_RANK:
        if _LEVEL_RANK[ceil] > _LEVEL_RANK[EXTERNAL_CEILING]:
            errs.append(f"AV-T5 external clamp: origin=external caps epistemic_ceiling at {EXTERNAL_CEILING}, got {ceil}")

    # AV-T6 emergence gate: expansion requires full coverage + stability
    if "expansion" in tr:
        cov = rec.get("coverage", {})
        if cov.get("ratio") != 1.0:
            errs.append("AV-T6 emergence: transform.expansion requires coverage.ratio == 1.0 (fully fibered)")
        if "stability" not in rec:
            errs.append("AV-T6 emergence: transform.expansion requires a stability block")

    # AV-T7 lifecycle coherence
    evi = life.get("eviction", {})
    if evi.get("policy", "none") != "none" and "window_seconds" not in life.get("freshness", {}):
        errs.append("AV-T7 lifecycle: eviction policy other than 'none' requires freshness.window_seconds")
    rec_blk = life.get("reconstruction", {})
    if rec_blk.get("deterministic") and not rec_blk.get("source_refs"):
        errs.append("AV-T7 lifecycle: deterministic reconstruction requires non-empty reconstruction.source_refs")

    return errs


def validate_record(rec: dict, schema, label: str) -> list[str]:
    import jsonschema
    errs = [f"{label}: schema: {e.message} (at /{'/'.join(map(str, e.path))})"
            for e in sorted(jsonschema.Draft202012Validator(schema).iter_errors(rec), key=lambda e: list(e.path))]
    errs += [f"{label}: {m}" for m in _cross_field(rec)]
    return errs


def main(argv: list[str]) -> int:
    try:
        import jsonschema  # noqa: F401
    except ImportError:
        print("ERR: pip install jsonschema", file=sys.stderr)
        return 2
    schema = json.loads(SCHEMA.read_text())
    targets = [Path(a) for a in argv[1:]] or sorted((ROOT / "examples").glob("*.json"))
    if not targets:
        print("no descriptors to validate", file=sys.stderr)
        return 2

    all_errs: list[str] = []
    for t in targets:
        rec = json.loads(t.read_text())
        errs = validate_record(rec, schema, t.name)
        expect_invalid = t.name.endswith(".invalid.json")
        if expect_invalid:
            # negative fixture: it MUST fail, else the guard has no teeth
            if not errs:
                all_errs.append(f"{t.name}: expected INVALID but it passed (guard has no teeth)")
            else:
                print(f"  ok   {t.name} correctly rejected ({errs[0].split(': ', 1)[1][:64]}…)")
        else:
            if errs:
                all_errs += errs
            else:
                print(f"  ok   {t.name} conforms")

    if all_errs:
        print("\nANALYSIS-VIEW CONFORMANCE FAILURES:")
        for e in all_errs:
            print(f"  - {e}")
        return 1
    print("\nOK: all analysis-view descriptors conform (AV-1)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
