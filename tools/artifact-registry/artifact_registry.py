"""Artifact-class registry AC-01..12 + enrichment/zone routing (MS-P6, Metadata Standards §4).

Each artifact class has a defined enrichment path through the WNZL zones (MS-P5): the class determines
which parsers run, which fields extract, and the zone path the artifact follows. Zone paths are validated
against the canonical WNZL zone order so the registry can never route to a non-existent or out-of-order
zone.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "zone-lifecycle"))
from zone_lifecycle import ZONES, _RANK as _ZONE_RANK  # noqa: E402  (MS-P5 is the zone authority)


class RegistryError(Exception):
    pass


# AC-ID → {name (== metadata-record artifact_class enum), source_formats, enrichments, zone_path}
REGISTRY: dict[str, dict] = {
    "AC-01": {"name": "RawLog", "source_formats": ["macOS Unified Log", ".logarchive", ".log", "syslog", "BSM audit"],
              "enrichments": ["timestamp extraction", "process tree", "subsystem/category index", "error frequency"],
              "zone_path": ["Landing", "Examination", "Integration"]},
    "AC-02": {"name": "ConsolePaste", "source_formats": ["RTF", "TXT"],
              "enrichments": ["timestamp from embedded lines", "process-name index", "panic-save detection", "dup detection via content hash"],
              "zone_path": ["Landing", "Examination", "Integration"]},
    "AC-03": {"name": "Spindump", "source_formats": ["TXT", "PDF"],
              "enrichments": ["process tree", "PID chain", "CPU accounting", "binary image hash table", "deadlock detection", "kernel address extraction"],
              "zone_path": ["Landing", "Examination", "Integration"]},
    "AC-04": {"name": "BinaryPlist", "source_formats": [".plist", ".state", ".db", "bplist"],
              "enrichments": ["bplist decode", "key/value extraction", "UUID identification", "CloudKit subscription parsing", "persistent identifier extraction"],
              "zone_path": ["Landing", "Examination", "Integration"]},
    "AC-05": {"name": "EmailThread", "source_formats": ["Gmail thread (JSON/HTML)", "EML", "MBOX"],
              "enrichments": ["actor extraction", "timestamp chain", "delivery status", "case number extraction", "attachment inventory", "recipient/CC mapping"],
              "zone_path": ["Landing", "Examination", "Integration", "Governed"]},
    "AC-06": {"name": "LegalFiling", "source_formats": ["PDF", "DOCX"],
              "enrichments": ["filing metadata", "recipient identification", "delivery status", "case/ticket number", "response tracking", "cross-ref to AC-05"],
              "zone_path": ["Landing", "Examination", "Integration", "Governed"]},
    "AC-07": {"name": "AnalysisReport", "source_formats": ["DOCX", "PDF", "Google Doc"],
              "enrichments": ["source-artifact citation extraction", "evidence shopping-list", "claim extraction", "version-chain identification", "date-range analysis"],
              "zone_path": ["Landing", "Examination", "Integration"]},
    "AC-08": {"name": "DerivedReport", "source_formats": ["DOCX", "PDF", "MD"],
              "enrichments": ["AC-07 enrichments", "human-vs-AI authorship", "methodology capture"],
              "zone_path": ["Landing", "Examination", "Integration", "Governed"]},
    "AC-09": {"name": "AuditRecord", "source_formats": ["BSM binary", "CSV", "TSV"],
              "enrichments": ["syscall sequence extraction", "UID/PID mapping", "file-access timeline", "privilege-escalation detection"],
              "zone_path": ["Landing", "Examination", "Integration"]},
    "AC-10": {"name": "NetworkCapture", "source_formats": ["PCAP", "PCAPNG", "RTF (whois/DNS)", "TXT (netstat/ss)"],
              "enrichments": ["endpoint extraction", "protocol identification", "timing analysis", "IP geolocation", "anomalous-endpoint flagging"],
              "zone_path": ["Landing", "Examination", "Integration"]},
    "AC-11": {"name": "FirmwareDump", "source_formats": ["BIN", "HEX", "raw binary"],
              "enrichments": ["header parsing", "entropy analysis", "known-good comparison", "signature verification"],
              "zone_path": ["Landing", "Examination"]},
    "AC-12": {"name": "AppleDataArchive", "source_formats": ["ZIP (Apple data export)"],
              "enrichments": ["account identifier extraction", "device association map", "subscription-state diff", "iCloud service inventory"],
              "zone_path": ["Landing", "Examination", "Integration", "Governed"]},
}

_BY_NAME = {v["name"]: k for k, v in REGISTRY.items()}


def _valid_zone_path(path: list[str]) -> bool:
    return (bool(path) and all(z in ZONES for z in path)
            and all(_ZONE_RANK[path[i]] < _ZONE_RANK[path[i + 1]] for i in range(len(path) - 1)))


def by_id(ac_id: str) -> dict:
    if ac_id not in REGISTRY:
        raise RegistryError(f"unknown artifact-class id {ac_id!r}")
    return REGISTRY[ac_id]


def by_name(name: str) -> dict:
    if name not in _BY_NAME:
        raise RegistryError(f"unknown artifact_class {name!r}")
    return REGISTRY[_BY_NAME[name]]


def enrichment_path(name: str) -> list[str]:
    return by_name(name)["enrichments"]


def zone_path(name: str) -> list[str]:
    return by_name(name)["zone_path"]


def validate_registry() -> list[str]:
    """Every class complete + every zone_path valid against the canonical WNZL order."""
    errs = []
    for ac, e in REGISTRY.items():
        for k in ("name", "source_formats", "enrichments", "zone_path"):
            if not e.get(k):
                errs.append(f"{ac}: missing {k}")
        if e.get("zone_path") and not _valid_zone_path(e["zone_path"]):
            errs.append(f"{ac}: invalid/out-of-order zone_path {e.get('zone_path')}")
    return errs
