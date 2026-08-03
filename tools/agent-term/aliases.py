"""Alias.Resolve — the command palette / alias registry for agent-term (WO-F of ADR-0001).

A small, versioned registry mapping short human aliases to triRPC verb invocations (the YubNub pattern,
reimplemented — no legacy PHP). `agent-term g rain` resolves to Graph.QueryCypher; the CLI then dispatches
the resolved verb. Unknown aliases are rejected (no silent fallthrough to a shell).
"""
from __future__ import annotations

from dataclasses import dataclass


class AliasError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


@dataclass(frozen=True)
class ResolvedVerb:
    verb: str                 # a triRPC verb, e.g. "Graph.QueryCypher"
    params: dict
    action_class: str         # "read" (safe) | "compute-use" (needs the controller/disposable VM)


# alias -> (verb, action_class, builder(args)->params). Builders keep param shaping in one place.
def _graph_query(args: list[str]) -> dict:
    if not args:
        raise AliasError("args-missing", "usage: g <lemma> [relation]")
    lemma = args[0]
    q = ("MATCH (h:Concept {form:$lemma})-[:CSKG*1..2 {relation:$rel}]->(t) RETURN t.form LIMIT 25"
         if len(args) > 1 else
         "MATCH (h:Concept {form:$lemma})-[:CSKG*1..2]->(t) RETURN t.form LIMIT 25")
    params = {"lemma": lemma}
    if len(args) > 1:
        params["rel"] = args[1]
    return {"query": q, "params": params}


def _ask(args: list[str]) -> dict:
    if not args:
        raise AliasError("args-missing", "usage: ask <question...>")
    return {"question": " ".join(args)}


def _run_vm(args: list[str]) -> dict:
    if not args:
        raise AliasError("args-missing", "usage: vm <command...>")
    return {"command": " ".join(args)}


_REGISTRY = {
    # alias : (verb, action_class, builder)
    "g":    ("Graph.QueryCypher", "read", _graph_query),
    "ask":  ("Sherlock.Scout",    "read", _ask),
    "vm":   ("ComputerUse.Run",   "compute-use", _run_vm),
}

REGISTRY_VERSION = "v0.1"


def resolve(command: str) -> ResolvedVerb:
    """Resolve `alias arg1 arg2 ...` into a triRPC verb + params. Raises AliasError on unknown alias."""
    parts = command.strip().split()
    if not parts:
        raise AliasError("empty", "empty command")
    alias, args = parts[0], parts[1:]
    if alias not in _REGISTRY:
        raise AliasError("unknown-alias", f"no alias {alias!r} (known: {', '.join(sorted(_REGISTRY))})")
    verb, action_class, builder = _REGISTRY[alias]
    return ResolvedVerb(verb=verb, params=builder(args), action_class=action_class)


def registry() -> dict:
    """Introspectable palette (for a UI / `agent-term help`)."""
    return {a: {"verb": v, "action_class": c} for a, (v, c, _) in sorted(_REGISTRY.items())}
