"""Versioned local persistence for guided-lesson progress."""

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import sqlite3


SCHEMA_VERSION = 5

# Digests of earlier published identifiers. Keep the former identities out of
# shipped source while allowing existing local progress to follow renamed lessons.
_RENAMED_IDS = {
    "22333edce264ad08a94e19532bac6eab5d987702020e0a78a58232f8de27863f": "bruno-scotch-first-ideas",
    "19c07d481d6067dba09285be8d887dea676e0fd00789ff4da6124f4857261da8": "olive-catalan-first-ideas",
    "af91366f4f5b007d39bb6bfd8213233702b4956a2d0230e46667e6c860a72757": "bruno-scotch-make-room",
    "f3689f832dffcdd904fcf58c9648e0b8fae8a297d72ae9aec2e097440db81c4b": "bruno-scotch-active-knight",
    "0a79f23ca9b9dfaf71653a9d4c50e6296fd347edc8ac8d3789c53bc8488dceab": "bruno-scotch-try-alone",
    "a66af892d26f4b0aad3d625113382009b4f4f4bf3b7d930d04ea9b5ae98e1681": "olive-catalan-bishop",
    "470a2bd5807f14e45c19fb10454063d0a8b8020a755cb8983345e55b6ce25263": "olive-catalan-king-safety",
    "33436c87550ed0e4880a0a32878d3d9319e4837032ce2078a2e273b9a5ef7d73": "olive-catalan-try-alone",
    "0ef1ed61cf83e9cc2fba05ba96b262bf587368e02d77a566a4ccdb25d6fae022": "bruno-scotch-practice",
    "578f1c7f46acc653496de99e2dc5faff7b7a4ebc9824aefffa11ef7cdd085781": "bruno-scotch-transfer",
    "dcf357da47099ca37534aa276eecd96ee38d09ac23d04f380edbf0cde89046f0": "olive-catalan-practice",
    "328b3c2c1381d5b1e4c4a3b1167b34898730fa146e11512cf7e5ecd7f8b7fa2c": "olive-catalan-transfer",
    "6b1f0bc5928795e9c4ea97f72e9cc35f5935a390ed95ed8b892f9471c38d7891": "scotch-example-game",
    "8bab32ce33f2b5f2ecfd607654982f76ae5dea9145ea2d50e639211b330b2a80": "catalan-example-game",
    "33d7099ea60bdda805d359cdab4f3fd358e66636043db6fcb0a70b5d2a049ef6": "coordination-study",
}


def _current_id(value):
    if isinstance(value, str):
        return _RENAMED_IDS.get(sha256(value.encode()).hexdigest(), value)
    if isinstance(value, list):
        return [_current_id(item) for item in value]
    if isinstance(value, dict):
        return {key: _current_id(item) for key, item in value.items()}
    return value


class ProgressStoreError(RuntimeError):
    """Progress data could not be opened without risking learner history."""


@dataclass(frozen=True)
class ProgressRecord:
    lesson_id: str
    content_revision: int
    step_index: int
    completed: bool
    attempts: int
    hints_used: int
    reveals: int
    successes: int
    updated_at: str
    active_assisted: bool = False


@dataclass(frozen=True)
class StepProgressRecord:
    lesson_id: str
    content_revision: int
    step_id: str
    attempts: int
    hints_used: int
    reveals: int
    outcome: str
    updated_at: str


def default_progress_path():
    base = os.environ.get("XDG_DATA_HOME")
    if not base:
        base = os.path.join(os.path.expanduser("~"), ".local", "share")
    return Path(base) / "uroschess" / "progress.sqlite3"


class ProgressStore:
    """Small SQLite store with an explicit schema version and transactions."""

    def __init__(self, path=None):
        self.path = Path(path) if path is not None else default_progress_path()
        try:
            if str(self.path) != ":memory:":
                self.path.parent.mkdir(parents=True, exist_ok=True)
            self.connection = sqlite3.connect(str(self.path))
            self.connection.row_factory = sqlite3.Row
            self._migrate()
            self._migrate_renamed_ids()
        except (OSError, sqlite3.Error) as error:
            raise ProgressStoreError(
                "cannot open progress database {}: {}".format(
                    self.path, error)) from error

    def _migrate(self):
        with self.connection:
            self.connection.execute(
                "CREATE TABLE IF NOT EXISTS schema_info (version INTEGER NOT NULL)")
            row = self.connection.execute(
                "SELECT version FROM schema_info LIMIT 1").fetchone()
            if row is None:
                self.connection.execute(
                    "INSERT INTO schema_info(version) VALUES (?)", (SCHEMA_VERSION,))
                version = SCHEMA_VERSION
            else:
                version = row["version"]
            if version == 1:
                self.connection.execute(
                    """CREATE TABLE lesson_progress_v2 (
                        lesson_id TEXT NOT NULL,
                        content_revision INTEGER NOT NULL,
                        step_index INTEGER NOT NULL,
                        completed INTEGER NOT NULL,
                        attempts INTEGER NOT NULL,
                        hints_used INTEGER NOT NULL,
                        reveals INTEGER NOT NULL,
                        successes INTEGER NOT NULL,
                        updated_at TEXT NOT NULL,
                        PRIMARY KEY (lesson_id, content_revision)
                    )""")
                self.connection.execute(
                    """INSERT INTO lesson_progress_v2
                       SELECT lesson_id, content_revision, step_index, completed,
                              attempts, hints_used, reveals, successes, updated_at
                       FROM lesson_progress""")
                self.connection.execute("DROP TABLE lesson_progress")
                self.connection.execute(
                    "ALTER TABLE lesson_progress_v2 RENAME TO lesson_progress")
                version = 2
                self.connection.execute("UPDATE schema_info SET version = 2")
            if version == 2:
                self.connection.execute(
                    """CREATE TABLE IF NOT EXISTS app_settings (
                        key TEXT PRIMARY KEY,
                        value TEXT NOT NULL
                    )""")
                version = 3
                self.connection.execute("UPDATE schema_info SET version = 3")
            if version == 3:
                self.connection.execute(
                    """CREATE TABLE IF NOT EXISTS step_progress (
                        lesson_id TEXT NOT NULL,
                        content_revision INTEGER NOT NULL,
                        step_id TEXT NOT NULL,
                        attempts INTEGER NOT NULL,
                        hints_used INTEGER NOT NULL,
                        reveals INTEGER NOT NULL,
                        outcome TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        PRIMARY KEY (lesson_id, content_revision, step_id)
                    )""")
                version = 4
                self.connection.execute("UPDATE schema_info SET version = 4")
            if version == 4:
                self.connection.execute(
                    "ALTER TABLE lesson_progress ADD COLUMN active_assisted INTEGER NOT NULL DEFAULT 0")
                # Schema 4 has only lifetime help totals. For unfinished work,
                # uncertainty must never be counted as an independent answer.
                self.connection.execute(
                    """UPDATE lesson_progress SET active_assisted = 1
                       WHERE completed = 0 AND (hints_used > 0 OR reveals > 0)""")
                version = 5
                self.connection.execute("UPDATE schema_info SET version = 5")
            if version != SCHEMA_VERSION:
                raise ProgressStoreError(
                    "progress schema version {} is not supported; data was left "
                    "unchanged at {}".format(version, self.path))
            self.connection.execute(
                """CREATE TABLE IF NOT EXISTS lesson_progress (
                    lesson_id TEXT NOT NULL,
                    content_revision INTEGER NOT NULL,
                    step_index INTEGER NOT NULL,
                    completed INTEGER NOT NULL,
                    attempts INTEGER NOT NULL,
                    hints_used INTEGER NOT NULL,
                    reveals INTEGER NOT NULL,
                    successes INTEGER NOT NULL,
                    updated_at TEXT NOT NULL,
                    active_assisted INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (lesson_id, content_revision)
                )""")
            self.connection.execute(
                """CREATE TABLE IF NOT EXISTS app_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )""")
            self.connection.execute(
                """CREATE TABLE IF NOT EXISTS step_progress (
                    lesson_id TEXT NOT NULL,
                    content_revision INTEGER NOT NULL,
                    step_id TEXT NOT NULL,
                    attempts INTEGER NOT NULL,
                    hints_used INTEGER NOT NULL,
                    reveals INTEGER NOT NULL,
                    outcome TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (lesson_id, content_revision, step_id)
                )""")

    def _migrate_renamed_ids(self):
        with self.connection:
            for table in ("lesson_progress", "step_progress"):
                rows = self.connection.execute(
                    "SELECT DISTINCT lesson_id FROM " + table).fetchall()
                for row in rows:
                    previous = row["lesson_id"]
                    current = _current_id(previous)
                    if current != previous:
                        self.connection.execute(
                            "UPDATE OR IGNORE " + table +
                            " SET lesson_id = ? WHERE lesson_id = ?",
                            (current, previous))
                        self.connection.execute(
                            "DELETE FROM " + table + " WHERE lesson_id = ?",
                            (previous,))
            rows = self.connection.execute(
                "SELECT key, value FROM app_settings").fetchall()
            for row in rows:
                try:
                    value = json.loads(row["value"])
                except json.JSONDecodeError:
                    continue
                current = _current_id(value)
                if current != value:
                    self.connection.execute(
                        "UPDATE app_settings SET value = ? WHERE key = ?",
                        (json.dumps(current), row["key"]))

    def load(self, lesson_id, content_revision=None):
        if content_revision is None:
            row = self.connection.execute(
                """SELECT * FROM lesson_progress WHERE lesson_id = ?
                   ORDER BY updated_at DESC, rowid DESC LIMIT 1""",
                (lesson_id,),
            ).fetchone()
        else:
            row = self.connection.execute(
                """SELECT * FROM lesson_progress
                   WHERE lesson_id = ? AND content_revision = ?""",
                (lesson_id, content_revision),
            ).fetchone()
        if row is None:
            return None
        return ProgressRecord(
            lesson_id=row["lesson_id"],
            content_revision=row["content_revision"],
            step_index=row["step_index"],
            completed=bool(row["completed"]),
            attempts=row["attempts"],
            hints_used=row["hints_used"],
            reveals=row["reveals"],
            successes=row["successes"],
            updated_at=row["updated_at"],
            active_assisted=bool(row["active_assisted"]),
        )

    def latest_unfinished(self, revisions):
        """Return the newest unfinished lesson still in the current pack."""
        rows = self.connection.execute(
            """SELECT lesson_id, content_revision FROM lesson_progress
               WHERE completed = 0 ORDER BY updated_at DESC, rowid DESC"""
        ).fetchall()
        for row in rows:
            if revisions.get(row["lesson_id"]) == row["content_revision"]:
                return self.load(row["lesson_id"], row["content_revision"])
        return None

    def load_step_progress(self, lesson_id, content_revision):
        rows = self.connection.execute(
            """SELECT * FROM step_progress WHERE lesson_id = ?
               AND content_revision = ? ORDER BY step_id""",
            (lesson_id, content_revision)).fetchall()
        return {row["step_id"]: StepProgressRecord(
            lesson_id=row["lesson_id"],
            content_revision=row["content_revision"],
            step_id=row["step_id"], attempts=row["attempts"],
            hints_used=row["hints_used"], reveals=row["reveals"],
            outcome=row["outcome"], updated_at=row["updated_at"])
            for row in rows}

    def save(self, controller):
        now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        values = (
            controller.lesson.lesson_id,
            controller.lesson.content_revision,
            controller.step_index,
            int(controller.state == "COMPLETED"),
            controller.attempts,
            controller.hints_used,
            controller.reveals,
            controller.successes,
            now,
            int(controller.assisted and controller.state != "COMPLETED"),
        )
        with self.connection:
            self.connection.execute(
                """INSERT INTO lesson_progress (
                       lesson_id, content_revision, step_index, completed,
                       attempts, hints_used, reveals, successes, updated_at,
                       active_assisted
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(lesson_id, content_revision) DO UPDATE SET
                       step_index=excluded.step_index,
                       completed=excluded.completed,
                       attempts=excluded.attempts,
                       hints_used=excluded.hints_used,
                       reveals=excluded.reveals,
                       successes=excluded.successes,
                       updated_at=excluded.updated_at,
                       active_assisted=excluded.active_assisted""",
                values,
            )
            for step_id, step in controller.step_progress.items():
                self.connection.execute(
                    """INSERT INTO step_progress (
                        lesson_id, content_revision, step_id, attempts,
                        hints_used, reveals, outcome, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(lesson_id, content_revision, step_id)
                    DO UPDATE SET attempts=excluded.attempts,
                        hints_used=excluded.hints_used,
                        reveals=excluded.reveals,
                        outcome=excluded.outcome,
                        updated_at=excluded.updated_at""",
                    (controller.lesson.lesson_id,
                     controller.lesson.content_revision, step_id,
                     step["attempts"], step["hints_used"], step["reveals"],
                     step["outcome"], now))
        return self.load(controller.lesson.lesson_id)

    def load_settings(self):
        """Return all persisted application preferences."""

        try:
            rows = self.connection.execute(
                "SELECT key, value FROM app_settings ORDER BY key").fetchall()
        except sqlite3.Error as error:
            raise ProgressStoreError(
                "cannot read preferences from {}: {}".format(
                    self.path, error)) from error
        settings = {}
        for row in rows:
            try:
                settings[row["key"]] = json.loads(row["value"])
            except (TypeError, ValueError) as error:
                raise ProgressStoreError(
                    "setting {!r} is unreadable in {}: {}".format(
                        row["key"], self.path, error)) from error
        return settings

    def save_settings(self, settings):
        """Persist a mapping of JSON-compatible application preferences."""

        values = []
        for key, value in settings.items():
            if not isinstance(key, str) or not key:
                raise ValueError("setting names must be non-empty strings")
            values.append((key, json.dumps(value, separators=(",", ":"))))
        try:
            with self.connection:
                self.connection.executemany(
                    """INSERT INTO app_settings(key, value) VALUES (?, ?)
                       ON CONFLICT(key) DO UPDATE SET value=excluded.value""",
                    values,
                )
        except sqlite3.Error as error:
            raise ProgressStoreError(
                "cannot save preferences to {}: {}".format(
                    self.path, error)) from error

    def close(self):
        self.connection.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
