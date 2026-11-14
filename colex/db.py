"""SQLite storage: one connection per thread, WAL mode, numbered migrations."""
from __future__ import annotations

import json
import sqlite3
import threading
from typing import Any

from colex import settings

_local = threading.local()

MIGRATIONS: list[str] = [
    """
    create table runs (run_id text primary key, law_id text not null, status text not null,
        current_node text not null, branches_json text not null default '{}', paused integer not null default 0,
        config_version_id text, map_version_id text, parent_checkpoint_id text, created_ts text not null,
        meta_json text not null default '{}');
    create table steps (run_id text not null, step_key text not null, branch_id text not null, node text not null,
        status text not null, output_ref text, checkpoint_id text, config_version_id text, ts text not null,
        primary key (run_id, step_key));
    create table checkpoints (checkpoint_id text primary key, run_id text not null, branch_id text not null,
        node text not null, step_key text not null, state_ref text not null, pending_json text not null default '[]',
        git_ref text, budgets_json text not null default '{}', config_version_id text, map_version_id text,
        parent_id text, ts text not null, seq integer not null);
    create table blobs (ref text primary key, body text not null);
    create table audit_events (id integer primary key autoincrement, run_id text, ts text not null,
        agent text not null, step text not null, kind text not null, summary text not null default '',
        detail_json text not null default '{}', input_ref text, output_ref text, tokens_in integer not null default 0,
        tokens_out integer not null default 0, cost_usd real not null default 0, duration_ms integer not null default 0,
        model text, checkpoint_id text, prev_hash text not null, hash text not null);
    create table side_effects (key text primary key, status text not null, result_json text, ts text not null);
    create table waits (wait_id text primary key, run_id text not null, branch_id text not null, kind text not null,
        payload_json text not null, status text not null, answer_json text, actor text, created_ts text not null,
        answered_ts text, seq_created integer not null, seq_answered integer);
    create table config_versions (version_id text primary key, hash text not null, author text not null,
        ts text not null, diff text not null default '', payload_json text not null, seq integer not null);
    create table llm_cache (key text primary key, response_json text not null, ts text not null);
    create table outbox (id integer primary key autoincrement, idem_key text unique not null, run_id text,
        channel text not null, kind text not null, payload_json text not null, status text not null,
        attempts integer not null default 0, next_attempt_at real not null default 0, slack_ts text,
        thread_ts text, error text, created_ts text not null);
    create table interactions (key text primary key, actor text, ts text not null);
    create table kv (key text primary key, value text not null);
    """,
    """
    create table laws (celex text primary key, sha text not null, body_sha text, title text not null,
        path text not null, status text not null, reason text, run_id text, triage_json text,
        doc_json text not null, ts text not null);
    """,
]


def connect() -> sqlite3.Connection:
    """Return this thread's connection to the current database, migrated."""
    path = str(settings.db_path())
    con = getattr(_local, "con", None)
    if con is not None and getattr(_local, "path", None) == path:
        return con
    if con is not None:
        con.close()
    settings.db_path().parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path, timeout=30, isolation_level=None)
    con.row_factory = sqlite3.Row
    con.execute("pragma journal_mode=wal")
    con.execute("pragma busy_timeout=30000")
    migrate(con)
    _local.con, _local.path = con, path
    return con


def migrate(con: sqlite3.Connection) -> int:
    version = con.execute("pragma user_version").fetchone()[0]
    for number in range(version, len(MIGRATIONS)):
        con.execute("begin immediate")
        try:
            if con.execute("pragma user_version").fetchone()[0] > number:
                con.execute("commit")
                continue
            for statement in MIGRATIONS[number].split(";"):
                if statement.strip():
                    con.execute(statement)
            con.execute(f"pragma user_version={number + 1}")
            con.execute("commit")
        except Exception:
            con.execute("rollback")
            raise
    return len(MIGRATIONS)


def dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def kv_get(key: str, default: str | None = None) -> str | None:
    row = connect().execute("select value from kv where key=?", (key,)).fetchone()
    return row["value"] if row else default


def kv_set(key: str, value: str) -> None:
    connect().execute("insert into kv(key,value) values(?,?) on conflict(key) do update set value=excluded.value",
                      (key, value))
