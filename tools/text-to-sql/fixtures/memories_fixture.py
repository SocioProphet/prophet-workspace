"""In-memory SQLite fixture mirroring the memoryd `memories` schema (consume-not-fork).

This stands up NO new database: it recreates the exact table+index DDL from
`prophet-platform/apps/memoryd/src/memoryd/sqlite_store.py` in an `:memory:` connection and seeds a
handful of deterministic rows, so a constructed query can be EXECUTED and its rows asserted. Read-only
use in the teeth (the connection is opened `query_only`).
"""
from __future__ import annotations

import sqlite3

# Verbatim shape from memoryd/sqlite_store.py (memories table + created_at index).
_DDL = """
CREATE TABLE memories (
    memory_id TEXT PRIMARY KEY,
    text_content TEXT NOT NULL,
    memory_class TEXT NOT NULL,
    tags_json TEXT NOT NULL,
    metadata_json TEXT NOT NULL,
    event_id TEXT NOT NULL,
    envelope_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    revoked INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX idx_memories_created_at ON memories(created_at DESC);
"""

_ROWS = [
    # memory_id, text_content, memory_class, tags, event_id, created_at
    ("m1", "coastal erosion accelerated along the shoreline", "fact", '["climate"]', "e1", "2020-03-01"),
    ("m2", "the team decided to prioritise coastal defence funding", "decision", '["policy"]', "e2", "2021-06-15"),
    ("m3", "user prefers metric units for erosion reports", "preference", '["ui"]', "e3", "2022-01-09"),
    ("m4", "storm surge modelling notes on erosion", "fact", '["climate"]', "e4", "2023-11-20"),
    ("m5", "summary of coastal erosion mitigation options", "summary", '["climate"]', "e5", "2025-02-02"),
    ("m6", "scratchpad: todo revisit tide gauges", "scratch", "[]", "e6", "2019-08-08"),
]


def make_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.executescript(_DDL)
    conn.executemany(
        "INSERT INTO memories(memory_id, text_content, memory_class, tags_json, metadata_json, "
        "event_id, envelope_json, created_at) VALUES (?,?,?,?,?,?,?,?)",
        [(mid, txt, cls, tags, "{}", eid, "{}", ts) for (mid, txt, cls, tags, eid, ts) in _ROWS],
    )
    conn.commit()
    # read-only from here on: a constructed query must never mutate the fixture
    conn.execute("PRAGMA query_only = ON")
    return conn
