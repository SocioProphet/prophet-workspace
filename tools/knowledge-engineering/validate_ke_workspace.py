#!/usr/bin/env python3
"""Validate KnowledgeEngineeringWorkspace records — the estate's Watson-Knowledge-Studio-equivalent teeth.

This is the composition layer's guard. The workbench does not invent an entity/relation/term model; it
BINDS the governed ones (consume-not-fork) and REFUSES a workspace that tries to smuggle an ungoverned one
back in:

  - entity/relation types are REFERENCED into the governed registries (regis entity-class #16,
    semantic-role-kind #22); a reference to a type NOT in a governed registry is rejected;
  - dictionary entries BIND governed Systema Concept Entries (ontogenesis Platform/Systema): source-
    anchored, promotion-state-lifecycled, revisioned. A "dictionary" that is really a static lookup list —
    mode=static_match, or an entry with NO sourceAnchor, or an entry promoted past review without a
    reviewed anchor — is rejected. This is 'learn, don't match dictionaries' made mechanical
    (feedback_learn_dont_match_dictionaries).
  - the user is a first-class author: add/overwrite/annotate/define is a governed AuthorshipEvent, author-
    attributed + versioned + receipted, overwriting the learned layer by supersession (prior retained).
    An override with no author or no receipt is rejected.

The teeth (cross-field rules pure JSON Schema can't state, enforced BOTH ways):

  KE-T1  learn-don't-match  — Dictionary.mode must be 'governed'; every DictionaryEntry must have a
                             sourceAnchor; promotionState must be a Systema lifecycle member; advancing
                             past 'reviewed_definition' requires a REVIEWED anchor; 'implementation_linked'
                             or beyond requires an implementationSurface. A bare word/tag (no anchor) or a
                             static_match dictionary is REJECTED.
  KE-T2  governed-registry types — every entity/relation TypeBinding references a known governed registry
                             ($id) and a member in that registry's enum. Unknown registry/member REJECTED.
  KE-T3  rule integrity   — every rule's entityTypeRefs/relationTypeRefs resolves to a TypeBinding in this
                             workspace (which, by KE-T2, resolves to the governed registry). Dangling ref
                             REJECTED.
  KE-T4  promotion receipt — an annotation with promotedTo set MUST carry promotionReceiptRef. A promotion
                             with no provenance receipt is REJECTED.
  KE-T5  authored supersession — an op=overwrite AuthorshipEvent MUST carry 'supersedes' (prior retained).
                             authored/overwritten WITH author+version+receipt+supersedes VERIFIES.
  KE-T6  override needs author+receipt — any AuthorshipEvent missing author.id or receiptRef is REJECTED.
  KE-T7  provenance + single-active — every governed artifact carries provenance.class {learned|
                             human_authored|imported} + a receiptRef; per conceptRef, exactly one active
                             (non-superseded/tombstoned) version, and it is the max version.
  KE-T8  receipt format   — every receiptRef is a governed receipt id: sha256:<64hex> (proof-artifact-
                             spine) or urn:srcos:receipt:... (knowledge-state-lifecycle). SHA-256 = FIPS-
                             180-4 algorithm.
  KE-T9  doc types        — documentSet docType in the WKS-supported set; a text doc over 2000 words is
                             rejected (keep docs small).

Dependency-light (no jsonschema library), matching this repo's convention. The published schema is
EXERCISED (validate_schema) so schema and code cannot silently drift.
Run: python3 tools/knowledge-engineering/validate_ke_workspace.py
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
SCHEMA = ROOT / "schemas/ke-workspace.schema.json"
EXAMPLES = ROOT / "examples"

# --- the governed registries this workbench CONSUMES (pinned; runtime follow-up re-syncs from source) ---
# regis-entity-graph entity-class (#16) and semantic-role-kind (#22). A TypeBinding must name one of these
# $ids AND a member in its enum — the workbench never lets an ungoverned type in through a rule.
GOVERNED_REGISTRIES: dict[str, set[str]] = {
    "https://socioprophet.org/schemas/regis/ner/entity-class.schema.json": {
        "PERSON", "ORG", "PRODUCT_SERVICE", "DEVICE", "ACCOUNT", "IDENTIFIER", "CREDENTIAL", "LOCATION",
        "JURISDICTION", "CONSENT_ARTIFACT", "POLICY_TERM", "PRIME_TOPIC_MENTION", "ACTION_EVENT_TRIGGER",
        "RELATIONSHIP_MENTION", "SCOPE_REALM", "TRACKING_IDENTIFIER", "HSM_HANDLE", "NONCE_STREAM",
        "EXPORT_ATTEMPT", "CONSENT_WITNESS", "SENSITIVE_CONTEXT", "CHILD_CONTEXT", "PATIENT_CONTEXT",
        "CIVIC_CONTEXT", "MARKETING_CONTEXT",
    },
    "https://socioprophet.org/schemas/regis/nlu/semantic-role-kind.schema.json": {
        "ACTION", "ENTITY_TYPE", "RELATION", "QUANTIFIER", "POSSESSION", "MODIFIER", "CONTEXT",
    },
}

# --- Systema Concept Entry lifecycle (ontogenesis Platform/Systema; CONSUMED verbatim) ---
PROMOTION_ORDER = [
    "observed_term", "extracted_candidate", "source_anchored", "reviewed_definition",
    "operational_definition", "implementation_linked", "tested_doctrine", "public_standard",
]
PROMOTION_SIDE = {"deprecated", "contested"}          # terminal side states (no lifecycle-skip check)
PROMOTION_STATES = set(PROMOTION_ORDER) | PROMOTION_SIDE
EXTRACTION_CONFIDENCE = {"A", "B", "C", "D", "E"}
REVIEW_STATES = {"unreviewed", "candidate", "manually_reviewed", "independently_verified", "rejected", "contested"}
REVIEWED = {"manually_reviewed", "independently_verified"}
QUOTE_BOUNDARY = {"exact", "near_verbatim", "paraphrase", "operational_translation", "analogy", "unsupported"}
ROLE_KINDS = {"ACTION", "ENTITY_TYPE", "RELATION", "QUANTIFIER", "POSSESSION", "MODIFIER", "CONTEXT"}
DOC_TYPES = {"CSV", "TXT", "PDF", "DOC", "DOCX", "HTML", "ZIP"}
TEXT_DOC_TYPES = {"CSV", "TXT", "HTML", "DOC", "DOCX"}  # word-count cap applies to text-bearing docs
PROVENANCE_CLASSES = {"learned", "human_authored", "imported"}

_RECEIPT = re.compile(r"^(sha256:[a-f0-9]{64}|urn:srcos:receipt:[A-Za-z0-9._:-]+)$")
_HANDLE = re.compile(r"^@[A-Za-z0-9-]+$")
_LABEL = re.compile(r"^[A-Z][A-Za-z0-9]*$")


class ValidationError(Exception):
    pass


def fail(message: str) -> None:
    raise ValidationError(message)


def load(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValidationError(f"missing file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValidationError(f"invalid JSON in {path}: {exc}") from exc


def _receipt(value: Any, ctx: str) -> None:
    if not isinstance(value, str) or not _RECEIPT.match(value):
        fail(f"KE-T8 {ctx}: receipt must be sha256:<64hex> or urn:srcos:receipt:... (got {value!r})")


def _provenance(prov: Any, ctx: str) -> str:
    """Validate a Provenance block; return its class. KE-T7 (class present + receipt) + KE-T8 (format)."""
    if not isinstance(prov, dict):
        fail(f"KE-T7 {ctx}: provenance must be an object")
    cls = prov.get("class")
    if cls not in PROVENANCE_CLASSES:
        fail(f"KE-T7 {ctx}: provenance.class must be one of {sorted(PROVENANCE_CLASSES)} (got {cls!r})")
    _receipt(prov.get("receiptRef"), f"{ctx}.provenance.receiptRef")
    if cls == "learned":
        lb = prov.get("learnedBy")
        if not (isinstance(lb, dict) and lb.get("predictor") and lb.get("evidence")):
            # a 'learned' artifact with no learned predictor+evidence is a static membership assertion
            fail(f"KE-T1 {ctx}: provenance.class=learned requires learnedBy.predictor + learnedBy.evidence "
                 f"(a learned term is a context-predictor decision, not a static list)")
    if cls == "human_authored":
        au = prov.get("author")
        if not (isinstance(au, dict) and isinstance(au.get("id"), str) and _HANDLE.match(au.get("id", ""))):
            fail(f"KE-T6 {ctx}: provenance.class=human_authored requires author.id (@handle)")
    if cls == "imported":
        im = prov.get("importedFrom")
        if not (isinstance(im, dict) and im.get("source") and im.get("license")):
            fail(f"KE-T7 {ctx}: provenance.class=imported requires importedFrom.source + license")
    return cls


def validate_dictionary_entry(entry: Any, ctx: str) -> None:
    """KE-T1: a governed Systema-bound entry; a static word/tag (no anchor) or a lifecycle-skip is rejected."""
    if not isinstance(entry, dict):
        fail(f"{ctx}: dictionary entry must be an object")
    if not entry.get("conceptRef"):
        fail(f"{ctx}: dictionary entry requires conceptRef (the bound Systema conceptId)")
    if not entry.get("prefLabel"):
        fail(f"{ctx}: dictionary entry requires prefLabel")

    # KE-T1: the source anchor is the learn-don't-match witness. No anchor => a bare word/tag => reject.
    anchor = entry.get("sourceAnchor")
    if not isinstance(anchor, dict):
        fail(f"KE-T1 {ctx}: dictionary entry has NO sourceAnchor — a static word/tag is not a governed "
             f"concept (learn, don't match dictionaries)")
    if not anchor.get("sourceRef"):
        fail(f"KE-T1 {ctx}: sourceAnchor.sourceRef is required")
    ec = anchor.get("extractionConfidence")
    if ec not in EXTRACTION_CONFIDENCE:
        fail(f"KE-T1 {ctx}: sourceAnchor.extractionConfidence must be one of {sorted(EXTRACTION_CONFIDENCE)}")
    rs = anchor.get("reviewState")
    if rs not in REVIEW_STATES:
        fail(f"KE-T1 {ctx}: sourceAnchor.reviewState must be one of {sorted(REVIEW_STATES)}")
    qb = anchor.get("quoteBoundary")
    if qb is not None and qb not in QUOTE_BOUNDARY:
        fail(f"KE-T1 {ctx}: sourceAnchor.quoteBoundary must be one of {sorted(QUOTE_BOUNDARY)}")

    state = entry.get("promotionState")
    if state not in PROMOTION_STATES:
        fail(f"KE-T1 {ctx}: promotionState must be a Systema lifecycle member (got {state!r})")

    if state in PROMOTION_ORDER:
        idx = PROMOTION_ORDER.index(state)
        # no skipping the lifecycle: past 'reviewed_definition' the anchor must actually be reviewed.
        if idx >= PROMOTION_ORDER.index("reviewed_definition") and rs not in REVIEWED:
            fail(f"KE-T1 {ctx}: promotionState {state!r} requires a reviewed sourceAnchor "
                 f"(reviewState in {sorted(REVIEWED)}), not {rs!r} — lifecycle cannot be skipped")
        # operational concept promotion requires an owning repo + implementation surface (Systema rule).
        if idx >= PROMOTION_ORDER.index("implementation_linked"):
            surf = entry.get("implementationSurface")
            if not (isinstance(surf, list) and surf and all(isinstance(s, dict) and s.get("ownerRepo") for s in surf)):
                fail(f"KE-T1 {ctx}: promotionState {state!r} requires implementationSurface with an ownerRepo")

    _provenance(entry.get("provenance"), ctx)


def _known_type_bindings(spec: dict) -> set[str]:
    ids: set[str] = set()
    for arr in ("entityTypes", "relationTypes"):
        for b in spec.get(arr, []) or []:
            if isinstance(b, dict) and b.get("bindingId"):
                ids.add(b["bindingId"])
    return ids


def validate_type_binding(binding: Any, ctx: str) -> None:
    """KE-T2: a type binding must reference a known governed registry ($id) and a member in its enum."""
    if not isinstance(binding, dict):
        fail(f"{ctx}: type binding must be an object")
    if not binding.get("bindingId"):
        fail(f"{ctx}: type binding requires bindingId")
    ref = binding.get("registryRef")
    if not isinstance(ref, dict):
        fail(f"KE-T2 {ctx}: type binding requires registryRef {{schemaId, member}}")
    schema_id, member = ref.get("schemaId"), ref.get("member")
    if schema_id not in GOVERNED_REGISTRIES:
        fail(f"KE-T2 {ctx}: registryRef.schemaId {schema_id!r} is NOT a governed registry "
             f"(known: {sorted(GOVERNED_REGISTRIES)})")
    if member not in GOVERNED_REGISTRIES[schema_id]:
        fail(f"KE-T2 {ctx}: {member!r} is not a member of governed registry {schema_id!r}")
    _provenance(binding.get("provenance"), ctx)


def resolve_active(workspace: dict, concept_ref: str) -> tuple[dict | None, str | None]:
    """Resolve the active dictionary entry for a conceptRef: the max-version entry whose status is not
    superseded/tombstoned, plus its provenance class. Returns (entry, provenance_class) or (None, None).
    This is the read side of supersession — a human overwrite raises the active version; prior is retained."""
    active: dict | None = None
    for d in workspace.get("spec", {}).get("dictionaries", []) or []:
        for e in d.get("entries", []) or []:
            if e.get("conceptRef") != concept_ref:
                continue
            if e.get("status") in ("superseded", "tombstoned"):
                continue
            if active is None or (e.get("version", 1) > active.get("version", 1)):
                active = e
    if active is None:
        return None, None
    return active, active.get("provenance", {}).get("class")


def _check_single_active(spec: dict) -> None:
    """KE-T7: for each conceptRef, at most one active (non-superseded/tombstoned) entry, and it is max version."""
    by_ref: dict[str, list[dict]] = {}
    for d in spec.get("dictionaries", []) or []:
        for e in d.get("entries", []) or []:
            by_ref.setdefault(e.get("conceptRef", ""), []).append(e)
    for ref, entries in by_ref.items():
        active = [e for e in entries if e.get("status") not in ("superseded", "tombstoned")]
        if len(active) > 1:
            fail(f"KE-T7: conceptRef {ref!r} has {len(active)} active versions — exactly one may be active "
                 f"(supersede the prior, don't leave two live)")
        if active and entries:
            max_v = max(e.get("version", 1) for e in entries)
            if active[0].get("version", 1) != max_v:
                fail(f"KE-T7: conceptRef {ref!r} active version {active[0].get('version')} is not the max "
                     f"version {max_v} — resolve must return the newest")


def validate_ke_workspace(record: Any) -> None:
    """Enforce the KEWorkspace envelope + KE-T1..T9. Raises ValidationError."""
    if not isinstance(record, dict):
        fail("record must be an object")
    if record.get("apiVersion") != "ke.socioprophet.dev/v1":
        fail("apiVersion must be ke.socioprophet.dev/v1")
    if record.get("kind") != "KnowledgeEngineeringWorkspace":
        fail("kind must be KnowledgeEngineeringWorkspace")

    meta = record.get("metadata")
    if not isinstance(meta, dict) or not meta.get("workspaceId"):
        fail("metadata.workspaceId required")
    owner = meta.get("owner")
    if not (isinstance(owner, str) and _HANDLE.match(owner)):
        fail("metadata.owner must be an @handle")
    created = meta.get("createdAt")
    try:
        datetime.fromisoformat(str(created).replace("Z", "+00:00"))
    except ValueError:
        fail("metadata.createdAt must be an RFC3339/ISO-8601 date-time")

    spec = record.get("spec")
    if not isinstance(spec, dict):
        fail("spec must be an object")

    # KE-T9 documents
    for i, doc in enumerate(spec.get("documentSet", []) or []):
        ctx = f"spec.documentSet[{i}]"
        if not isinstance(doc, dict) or not doc.get("docId"):
            fail(f"{ctx}: docId required")
        if doc.get("docType") not in DOC_TYPES:
            fail(f"KE-T9 {ctx}: docType must be one of {sorted(DOC_TYPES)}")
        wc = doc.get("wordCount")
        if isinstance(wc, int) and doc.get("docType") in TEXT_DOC_TYPES and wc > 2000:
            fail(f"KE-T9 {ctx}: wordCount {wc} exceeds 2000 — keep docs small (~1-2k words)")

    # KE-T2 governed types
    for i, b in enumerate(spec.get("entityTypes", []) or []):
        validate_type_binding(b, f"spec.entityTypes[{i}]")
    for i, b in enumerate(spec.get("relationTypes", []) or []):
        validate_type_binding(b, f"spec.relationTypes[{i}]")

    # KE-T1 dictionaries (learn-don't-match)
    for i, d in enumerate(spec.get("dictionaries", []) or []):
        ctx = f"spec.dictionaries[{i}]"
        if not isinstance(d, dict) or not d.get("dictionaryId"):
            fail(f"{ctx}: dictionaryId required")
        if d.get("mode") != "governed":
            fail(f"KE-T1 {ctx}: dictionary mode must be 'governed'; a static_match lookup dictionary is "
                 f"rejected (learn, don't match dictionaries) — got {d.get('mode')!r}")
        for j, e in enumerate(d.get("entries", []) or []):
            validate_dictionary_entry(e, f"{ctx}.entries[{j}]")

    # KE-T7 single-active-version
    _check_single_active(spec)

    # KE-T8 version snapshots are receipted
    for i, v in enumerate(spec.get("versions", []) or []):
        ctx = f"spec.versions[{i}]"
        if not isinstance(v, dict) or not v.get("versionId"):
            fail(f"{ctx}: versionId required")
        _receipt(v.get("receiptRef"), f"{ctx}.receiptRef")

    # KE-T3 rule integrity
    known = _known_type_bindings(spec)
    for i, r in enumerate(spec.get("rules", []) or []):
        ctx = f"spec.rules[{i}]"
        if not isinstance(r, dict) or not r.get("ruleId"):
            fail(f"{ctx}: ruleId required")
        for ref in (r.get("entityTypeRefs", []) or []) + (r.get("relationTypeRefs", []) or []):
            if ref not in known:
                fail(f"KE-T3 {ctx}: references type binding {ref!r} not present in this workspace "
                     f"(so it does not resolve to a governed registry)")
        _provenance(r.get("provenance"), ctx)

    # KE-T4 annotation promotion receipts
    for i, a in enumerate(spec.get("annotations", []) or []):
        ctx = f"spec.annotations[{i}]"
        if not isinstance(a, dict) or not a.get("annotationId"):
            fail(f"{ctx}: annotationId required")
        role = a.get("role")
        if not isinstance(role, dict) or role.get("kind") not in ROLE_KINDS or not _LABEL.match(str(role.get("label", ""))):
            fail(f"{ctx}: role must have a learned label (UpperCamelCase) + a governed kind")
        promoted = a.get("promotedTo")
        if promoted is not None:
            if not isinstance(promoted, dict) or not promoted.get("ref"):
                fail(f"{ctx}: promotedTo requires targetKind + ref")
            _receipt(a.get("promotionReceiptRef"),
                     f"KE-T4 {ctx}: an annotation promoted to {promoted.get('targetKind')} requires "
                     f"promotionReceiptRef")

    # KE-T5/T6 human authorship events
    for i, ev in enumerate(spec.get("authorship", []) or []):
        ctx = f"spec.authorship[{i}]"
        if not isinstance(ev, dict) or not ev.get("eventId"):
            fail(f"{ctx}: eventId required")
        if ev.get("op") not in {"add", "overwrite", "annotate", "define"}:
            fail(f"{ctx}: op must be add|overwrite|annotate|define")
        if ev.get("provenanceClass") != "human_authored":
            fail(f"{ctx}: authorship provenanceClass must be human_authored")
        # KE-T6: an override with no author or no receipt is rejected.
        au = ev.get("author")
        if not (isinstance(au, dict) and isinstance(au.get("id"), str) and _HANDLE.match(au.get("id", ""))):
            fail(f"KE-T6 {ctx}: authorship event requires author.id (@handle) — no anonymous overrides")
        _receipt(ev.get("receiptRef"), f"KE-T6 {ctx}: authorship event requires receiptRef")
        if not isinstance(ev.get("version"), int) or ev.get("version") < 1:
            fail(f"KE-T5 {ctx}: authorship event requires an integer version >= 1")
        # KE-T5: an overwrite supersedes a prior version (retained).
        if ev.get("op") == "overwrite" and not ev.get("supersedes"):
            fail(f"KE-T5 {ctx}: an overwrite MUST carry 'supersedes' (the prior version is retained, "
                 f"not deleted)")


def validate_schema(schema: Any) -> None:
    """Exercise the published schema and assert it stays in lockstep with the validator, so the two cannot
    silently drift (dependency-light, per repo convention)."""
    if not isinstance(schema, dict):
        fail("schema must be an object")
    if schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
        fail("schema must use JSON Schema draft 2020-12")
    if schema.get("additionalProperties") is not False:
        fail("schema root must be strict (additionalProperties:false)")
    props = schema.get("properties", {})
    if props.get("kind", {}).get("const") != "KnowledgeEngineeringWorkspace":
        fail("schema kind const mismatch")
    defs = schema.get("$defs", {})
    # provenance classes lockstep
    pc = set(defs.get("Provenance", {}).get("properties", {}).get("class", {}).get("enum", []))
    if pc != PROVENANCE_CLASSES:
        fail("schema Provenance.class enum drifted from validator PROVENANCE_CLASSES")
    # Systema lifecycle lockstep (dictionary entry promotionState)
    de = defs.get("DictionaryEntry", {}).get("properties", {})
    if set(de.get("promotionState", {}).get("enum", [])) != PROMOTION_STATES:
        fail("schema DictionaryEntry.promotionState enum drifted from validator PROMOTION_STATES")
    if de.get("sourceAnchor", {}).get("type") != "object":
        fail("schema DictionaryEntry.sourceAnchor must be an object (KE-T1 anchor witness)")
    if "sourceAnchor" not in defs.get("DictionaryEntry", {}).get("required", []):
        fail("schema DictionaryEntry must REQUIRE sourceAnchor (KE-T1)")
    ec = set(de.get("sourceAnchor", {}).get("properties", {}).get("extractionConfidence", {}).get("enum", []))
    if ec != EXTRACTION_CONFIDENCE:
        fail("schema sourceAnchor.extractionConfidence enum drifted from validator EXTRACTION_CONFIDENCE")
    # dictionary mode must be the const 'governed' (static_match rejected by construction)
    if defs.get("Dictionary", {}).get("properties", {}).get("mode", {}).get("const") != "governed":
        fail("schema Dictionary.mode must be const 'governed' (KE-T1)")
    # doc types lockstep
    dt = set(defs.get("DocumentRef", {}).get("properties", {}).get("docType", {}).get("enum", []))
    if dt != DOC_TYPES:
        fail("schema DocumentRef.docType enum drifted from validator DOC_TYPES")
    # authorship requires author + receipt + version (KE-T6/T5)
    ae_req = set(defs.get("AuthorshipEvent", {}).get("required", []))
    if not {"author", "receiptRef", "version", "op"} <= ae_req:
        fail("schema AuthorshipEvent must require author, receiptRef, version, op (KE-T5/T6)")
    # receipt format lockstep
    if defs.get("ReceiptRef", {}).get("pattern") != _RECEIPT.pattern:
        fail("schema ReceiptRef pattern drifted from validator receipt regex (KE-T8)")


def main() -> int:
    try:
        validate_schema(load(SCHEMA))                 # schema is exercised, not just parsed
        files = sorted(EXAMPLES.glob("*.json"))
        valids = [f for f in files if f.name.endswith(".valid.json")]
        invalids = [f for f in files if f.name.endswith(".invalid.json")]
        if not valids or not invalids:
            fail("examples/ must contain both *.valid.json and *.invalid.json fixtures")
        for path in valids:
            try:
                validate_ke_workspace(load(path))
            except ValidationError as exc:
                fail(f"expected {path.name} to PASS, but it was rejected: {exc}")
        for path in invalids:
            try:
                validate_ke_workspace(load(path))
            except ValidationError:
                continue
            fail(f"expected {path.name} to be REJECTED, but it passed")
    except ValidationError as exc:
        print(f"ERR: {exc}", file=sys.stderr)
        return 2
    print(f"OK: KnowledgeEngineeringWorkspace validation passed ({len(valids)} valid, "
          f"{len(invalids)} invalid rejected)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
