"""Per-host persistence of subject answers under the release the remote service states."""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
from collections.abc import Callable, Iterator, Sequence
from contextlib import closing, contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from itertools import batched
from pathlib import Path
from typing import Any

from just_dna_enricher.locations import ANSWER_STORE_FILENAME, answer_store_path

logger = logging.getLogger(__name__)


class AnswerStore:
    """A lazy SQLite file. Each operation owns its connection and each batch write one transaction."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self._lock = threading.Lock()
        self._ready = False
        self._failed = False

    def _access[T](self, operation: Callable[[sqlite3.Connection], T], fallback: T) -> T:
        with self._lock:
            if not self._failed:
                try:
                    path = self.path
                    if path.is_dir():
                        path = path / ANSWER_STORE_FILENAME
                    if not self._ready:
                        path.parent.mkdir(parents=True, exist_ok=True)
                    with closing(sqlite3.connect(path, timeout=15)) as db:
                        if not self._ready:
                            self._initialize(db)
                            self._ready = True
                        with db:
                            return operation(db)
                except (OSError, sqlite3.Error, ValueError) as exc:
                    self._failed = True
                    logger.warning("Answer store %s unavailable (%s). Continuing live.", self.path, exc)
            return fallback

    @staticmethod
    def _initialize(db: sqlite3.Connection) -> None:
        # Two first openers can both hold a read lock while changing journal mode. Wait for
        # the other writer using SQLite's busy timeout before retrying that lock upgrade.
        try:
            db.execute("PRAGMA journal_mode=WAL").fetchone()
        except sqlite3.OperationalError as exc:
            if exc.sqlite_errorcode != sqlite3.SQLITE_BUSY:
                raise
            db.execute("BEGIN IMMEDIATE")
            db.commit()
            db.execute("PRAGMA journal_mode=WAL").fetchone()
        db.execute("""CREATE TABLE IF NOT EXISTS answers (
            source TEXT NOT NULL, release TEXT NOT NULL, request_key TEXT NOT NULL,
            answer TEXT NOT NULL, absent INTEGER NOT NULL, stored_at TEXT NOT NULL,
            PRIMARY KEY (source, release, request_key)
        ) WITHOUT ROWID""")

    def read(self, source: str, release: str, keys: Sequence[str]) -> dict[str, Any]:
        def select(db: sqlite3.Connection) -> dict[str, Any]:
            found = {}
            for chunk in batched(keys, 500, strict=False):
                slots = ",".join("?" for _ in chunk)
                rows = db.execute(
                    f"SELECT request_key, answer FROM answers WHERE source=? AND release=? "
                    f"AND request_key IN ({slots})",
                    (source, release, *chunk),
                )
                found.update((key, json.loads(answer)) for key, answer in rows)
            return found

        return self._access(select, {})

    def write(self, source: str, release: str, rows: dict[str, tuple[Any, bool]]) -> None:
        def insert(db: sqlite3.Connection) -> None:
            db.executemany(
                """INSERT OR REPLACE INTO answers (source, release, request_key, answer, absent, stored_at)
                   VALUES (?, ?, ?, ?, ?, strftime('%Y-%m-%dT%H:%M:%fZ','now'))""",
                ((source, release, key, json.dumps(value), absent) for key, (value, absent) in rows.items()),
            )

        self._access(insert, None)


type StoreSetting = AnswerStore | Path | str | bool | None


@dataclass
class AnswerUsage:
    source: str
    release: str | None
    stored: int = 0
    live: int = 0

    def __str__(self) -> str:
        return f"Answer store {self.source} release={self.release or 'unknown'} stored={self.stored} live={self.live}"


class AnswerRun:
    """One set of release observations and counters. A shared client uses its caller's active run."""

    def __init__(self, setting: StoreSetting = None) -> None:
        if setting is True:
            raise ValueError("answer_store takes a store, a path, False or None")
        if isinstance(setting, AnswerStore):
            self.store = setting
        else:
            path = (
                None
                if setting is False
                else answer_store_path(Path(setting) if setting is not None else None)
            )
            self.store = AnswerStore(path) if path is not None else None
        self._releases: dict[str, str | None] = {}
        self._usage: dict[tuple[str, str | None], AnswerUsage] = {}
        self._lock = threading.Lock()

    def current(self) -> AnswerRun:
        return _ACTIVE.get() or self

    def release(self, source: str, probe: Callable[[], str | None]) -> str | None:
        with self._lock:
            if source not in self._releases:
                self._releases[source] = probe()
                if self._releases[source] is None and self.store is not None:
                    logger.warning(
                        "%s stated no usable release. Bypassing the answer store for this run.", source
                    )
            return self._releases[source]

    def count(self, source: str, release: str | None, *, stored: int = 0, live: int = 0) -> None:
        with self._lock:
            key = (source, release)
            if key not in self._usage:
                self._usage[key] = AnswerUsage(source, release)
            self._usage[key].stored += stored
            self._usage[key].live += live

    def report(self) -> list[AnswerUsage]:
        return sorted(self._usage.values(), key=lambda u: (u.source, u.release or ""))


@dataclass
class SourceAnswers:
    run: AnswerRun
    source: str
    release: str | None
    prefix: str = ""

    def read(self, keys: Sequence[str]) -> dict[str, Any]:
        if not keys or self.release is None or self.run.store is None:
            return {}
        found = self.run.store.read(self.source, self.release, [self.prefix + k for k in keys])
        if found:
            self.run.count(self.source, self.release, stored=len(found))
        return {k.removeprefix(self.prefix): v for k, v in found.items()}

    def asked(self, subjects: int = 1) -> None:
        self.run.count(self.source, self.release, live=subjects)

    def write(self, rows: dict[str, tuple[Any, bool]]) -> None:
        if rows and self.release is not None and self.run.store is not None:
            self.run.store.write(self.source, self.release, {self.prefix + k: v for k, v in rows.items()})


_ACTIVE: ContextVar[AnswerRun | None] = ContextVar("live_answer_run", default=None)


@contextmanager
def answer_run(setting: StoreSetting = None) -> Iterator[AnswerRun]:
    """Isolate concurrent enrich calls, including those borrowing exactly the same live clients."""
    parent = _ACTIVE.get()
    if setting is None and parent is not None:
        setting = parent.store if parent.store is not None else False
    run = AnswerRun(setting)
    token = _ACTIVE.set(run)
    try:
        yield run
    finally:
        _ACTIVE.reset(token)
