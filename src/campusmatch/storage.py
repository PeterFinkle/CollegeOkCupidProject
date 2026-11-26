"""Profile repositories: an in-memory store and a SQLite store with the same interface.

The API only ever calls `add`, `add_many`, `get`, `all` and `len()`, described by
`ProfileStore`. That narrow seam is what lets the app run on a dict in tests and on a file on
disk in production without the endpoints knowing the difference.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from os import PathLike
from pathlib import Path
from threading import Lock
from typing import Protocol, runtime_checkable

from .models import Answer, Importance, Profile


@runtime_checkable
class ProfileStore(Protocol):
    def add(self, p: Profile) -> None: ...
    def add_many(self, profiles: Iterable[Profile]) -> None: ...
    def get(self, pid: str) -> Profile | None: ...
    def all(self) -> list[Profile]: ...
    def __len__(self) -> int: ...


class Store:
    """Thread-safe in-memory repository. Fast and disposable: everything is lost on restart."""

    def __init__(self) -> None:
        self._profiles: dict[str, Profile] = {}
        self._lock = Lock()

    def add(self, p: Profile) -> None:
        with self._lock:
            self._profiles[p.id] = p

    def add_many(self, profiles: Iterable[Profile]) -> None:
        with self._lock:
            self._profiles.update((p.id, p) for p in profiles)

    def get(self, pid: str) -> Profile | None:
        with self._lock:
            return self._profiles.get(pid)

    def all(self) -> list[Profile]:
        with self._lock:
            return list(self._profiles.values())

    def __len__(self) -> int:
        with self._lock:
            return len(self._profiles)


_SCHEMA = """
CREATE TABLE IF NOT EXISTS profiles (
    id    TEXT PRIMARY KEY,
    name  TEXT NOT NULL,
    major TEXT NOT NULL DEFAULT '',
    year  INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS answers (
    profile_id  TEXT NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    question_id TEXT NOT NULL,
    choice      INTEGER NOT NULL,
    acceptable  INTEGER NOT NULL,  -- bitmask: bit i set means option i is acceptable
    importance  INTEGER NOT NULL,  -- Importance weight (0, 1, 10, 50, 250)
    PRIMARY KEY (profile_id, question_id)
) WITHOUT ROWID;
"""


class SQLiteStore:
    """Profile repository backed by a SQLite file, using only the standard library.

    One connection is shared by all threads and guarded by a lock. FastAPI runs sync
    endpoints in a threadpool, and sqlite3 connections refuse cross-thread use by default
    (`check_same_thread`); the lock is what makes turning that check off safe. SQLite
    serializes writers anyway, so a single connection costs little at this scale.

    `add` is an upsert: saving a profile with an existing id replaces its fields and its
    whole answer set, matching the in-memory store's dict semantics.

    Bitmasks are stored in a signed 64-bit INTEGER, so questions are limited to 63 options.
    """

    def __init__(self, path: str | PathLike[str] = ":memory:") -> None:
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._lock = Lock()
        with self._lock, self._conn:
            self._conn.execute("PRAGMA foreign_keys = ON")
            # WAL lets readers in other processes proceed during a write and makes each
            # commit an append instead of a full journal rewrite. Ignored for :memory:.
            self._conn.execute("PRAGMA journal_mode = WAL")
            self._conn.executescript(_SCHEMA)

    def add(self, p: Profile) -> None:
        self.add_many([p])

    def add_many(self, profiles: Iterable[Profile]) -> None:
        """Save several profiles in one transaction (one commit instead of one per profile)."""
        with self._lock, self._conn:
            for p in profiles:
                self._conn.execute(
                    "INSERT INTO profiles (id, name, major, year) VALUES (?, ?, ?, ?) "
                    "ON CONFLICT(id) DO UPDATE SET "
                    "name = excluded.name, major = excluded.major, year = excluded.year",
                    (p.id, p.name, p.major, p.year),
                )
                self._conn.execute("DELETE FROM answers WHERE profile_id = ?", (p.id,))
                self._conn.executemany(
                    "INSERT INTO answers (profile_id, question_id, choice, acceptable, importance)"
                    " VALUES (?, ?, ?, ?, ?)",
                    [
                        (p.id, a.question_id, a.choice, a.acceptable_mask, int(a.importance))
                        for a in p.answers.values()
                    ],
                )

    def get(self, pid: str) -> Profile | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT id, name, major, year FROM profiles WHERE id = ?", (pid,)
            ).fetchone()
            if row is None:
                return None
            answers = self._conn.execute(
                "SELECT profile_id, question_id, choice, acceptable, importance FROM answers "
                "WHERE profile_id = ? ORDER BY question_id",
                (pid,),
            ).fetchall()
        p = Profile(*row)
        for _, *answer in answers:
            p.answer(_to_answer(*answer))
        return p

    def all(self) -> list[Profile]:
        # Two queries instead of one per profile: the answers table is read in one pass and
        # attached to profiles by id.
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, name, major, year FROM profiles ORDER BY id"
            ).fetchall()
            answers = self._conn.execute(
                "SELECT profile_id, question_id, choice, acceptable, importance FROM answers "
                "ORDER BY profile_id, question_id"
            ).fetchall()
        profiles = {row[0]: Profile(*row) for row in rows}
        for pid, *answer in answers:
            profiles[pid].answer(_to_answer(*answer))
        return list(profiles.values())

    def __len__(self) -> int:
        with self._lock:
            return self._conn.execute("SELECT COUNT(*) FROM profiles").fetchone()[0]

    def close(self) -> None:
        with self._lock:
            self._conn.close()


def _to_answer(question_id: str, choice: int, acceptable: int, importance: int) -> Answer:
    return Answer(question_id, choice, Answer.options_from_mask(acceptable), Importance(importance))
