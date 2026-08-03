"""agent-term dispatch — resolve an alias to a triRPC verb and route it (WO-F of ADR-0001).

`agent-term g rain`  -> Alias.Resolve -> Graph.QueryCypher (WO-A gateway)
`agent-term vm <cmd>` -> Alias.Resolve -> ComputerUse.Run (disposable-VM controller, WO-F)
`agent-term ask <q>`  -> routes to Sherlock Scout (WO-D)

Thin by design: aliases + the safety controller carry the logic; this just routes.
"""
from __future__ import annotations

import os
import sys

_TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_TOOLS, "cypher-atomspace-gateway"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from aliases import resolve                    # noqa: E402
from controller import ComputerUseController   # noqa: E402
from gateway import query_cypher               # noqa: E402  (WO-A)


class DispatchError(Exception):
    pass


def dispatch(command: str, *, graph_adapter=None, controller: "ComputerUseController | None" = None):
    """Resolve + route a command. Returns the verb's result. Raises AliasError / DispatchError."""
    rv = resolve(command)
    if rv.verb == "Graph.QueryCypher":
        if graph_adapter is None:
            raise DispatchError("no-graph-adapter: Graph.QueryCypher needs a bound graph adapter")
        res = query_cypher(rv.params["query"], rv.params["params"], graph_adapter)
        return {"verb": rv.verb, "rows": res.rows, "plan": res.plan}
    if rv.verb == "ComputerUse.Run":
        if controller is None:
            raise DispatchError("no-controller: ComputerUse.Run needs a bound disposable-VM controller")
        return {"verb": rv.verb, **controller.run(rv.params["command"])}
    if rv.verb == "Sherlock.Scout":
        # routed to WO-D scout by the caller (needs mount table + graph + ledger); surfaced, not executed here
        return {"verb": rv.verb, "route": "sherlock-scout", "question": rv.params["question"]}
    raise DispatchError(f"unroutable verb {rv.verb}")


if __name__ == "__main__":  # pragma: no cover — live CLI needs bound adapters/controller
    print("agent-term: bind a graph adapter + disposable-VM controller to dispatch. See README.")
