"""SQLite lesson-progress persistence checks."""

from dataclasses import replace
import os
import sqlite3
import json

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from chess_game.study import LessonController, ProgressStore, load_game_library
from chess_game.study import progress as progress_module


def test_renamed_lessons_preserve_saved_progress_and_browse_route(tmp_path, monkeypatch):
    path = tmp_path / "progress.sqlite3"
    with ProgressStore(path) as store:
        with store.connection:
            store.connection.execute(
                """INSERT INTO lesson_progress VALUES
                   ('previous-lesson', 2, 1, 0, 3, 1, 0, 1, '2026-01-01', 1)""")
            store.connection.execute(
                """INSERT INTO step_progress VALUES
                   ('previous-lesson', 2, 'first', 3, 1, 0, 'helped', '2026-01-01')""")
            store.connection.execute(
                "INSERT INTO app_settings VALUES (?, ?)",
                ("last_learn_browse", json.dumps({"focus_id": "previous-lesson"})))
    original = progress_module._current_id
    monkeypatch.setattr(progress_module, "_current_id",
                        lambda value: ("current-lesson" if value == "previous-lesson"
                                       else {key: "current-lesson" for key in value}
                                       if isinstance(value, dict) else original(value)))
    with ProgressStore(path) as store:
        assert store.load("current-lesson").attempts == 3
        assert store.load_step_progress("current-lesson", 2)["first"].outcome == "helped"
        assert store.load_settings()["last_learn_browse"]["focus_id"] == "current-lesson"


def _controller():
    entry = next(entry for entry in load_game_library().entries
                 if entry.game.game_id == "coordination-study")
    return LessonController(entry.game, entry.lesson)


def test_progress_round_trip_and_update(tmp_path):
    controller = _controller()
    controller.begin_question()
    controller.request_hint()
    controller.attempt_uci("f8g7")
    controller.continue_lesson()

    path = tmp_path / "state" / "progress.sqlite3"
    with ProgressStore(path) as store:
        first = store.save(controller)
        assert first.step_index == 1
        assert first.attempts == 1
        assert first.hints_used == 1
        assert not first.completed

        controller.begin_question()
        controller.reveal()
        second = store.save(controller)
        assert second.reveals == 1
        assert second.updated_at >= first.updated_at

    with ProgressStore(path) as reopened:
        loaded = reopened.load(controller.lesson.lesson_id)
        assert loaded.step_index == 1
        assert loaded.content_revision == controller.lesson.content_revision
        assert loaded.successes == 1


def test_completed_progress_survives_restart(tmp_path):
    controller = _controller()
    for _ in range(3):
        controller.begin_question()
        controller.reveal()
        controller.continue_lesson()
    with ProgressStore(tmp_path / "progress.sqlite3") as store:
        store.save(controller)
    with ProgressStore(tmp_path / "progress.sqlite3") as store:
        record = store.load(controller.lesson.lesson_id)
        assert record.completed
        assert record.step_index == 2
        assert record.reveals == 3


def test_continue_learning_selects_latest_current_unfinished_lesson(tmp_path):
    from chess_game.ui import ChessUI
    import pygame

    ui = ChessUI(tmp_path / "progress.sqlite3")
    entries = [item for item in ui.game_library.entries if item.lesson]
    first, second = entries[:2]
    ui.start_lesson(first)
    ui._leave_lesson()
    ui.start_lesson(second)
    ui._leave_lesson()

    assert ui._resume_entry().lesson.lesson_id == second.lesson.lesson_id
    ui._continue_learning()
    assert ui.lesson.lesson.lesson_id == second.lesson.lesson_id

    revisions = {item.lesson.lesson_id: item.lesson.content_revision
                 for item in entries}
    revisions[second.lesson.lesson_id] += 1
    assert (ui.progress_store.latest_unfinished(revisions).lesson_id
            == first.lesson.lesson_id)
    ui.progress_store.close()


def test_new_learner_starts_with_opening_basics_and_sees_path(tmp_path):
    from chess_game.ui import ChessUI
    import pygame

    ui = ChessUI(tmp_path / "new-progress.sqlite3")
    ui._continue_learning()
    assert ui.lesson.lesson.lesson_id == "opening-essentials"
    assert ui._next_path_entry().lesson.lesson_id == "italian-development"
    ui._to_menu()
    ui._open_library("path")
    ui._build_menu_buttons()
    entries = [button for button in ui._menu_buttons
               if button.kind == "library"]
    assert entries[0].label == "Start with a useful plan"
    assert entries[0].detail.startswith("IN PROGRESS")
    ui.progress_store.close()
    pygame.quit()


def test_new_content_revision_preserves_completed_history(tmp_path):
    original = _controller()
    for _ in range(3):
        original.begin_question()
        original.reveal()
        original.continue_lesson()
    path = tmp_path / "revision-progress.sqlite3"
    with ProgressStore(path) as store:
        store.save(original)
        revised_lesson = replace(
            original.lesson, content_revision=original.lesson.content_revision + 1)
        revised = LessonController(
            original.game, revised_lesson,
            progress_totals={
                "attempts": original.attempts,
                "hints_used": original.hints_used,
                "reveals": original.reveals,
                "successes": original.successes,
            })
        store.save(revised)
        old = store.load(original.lesson.lesson_id,
                         original.lesson.content_revision)
        new = store.load(revised.lesson.lesson_id,
                         revised.lesson.content_revision)
        assert old.completed
        assert not new.completed and new.step_index == 0
        assert new.reveals == old.reveals


def test_schema_one_is_migrated_without_losing_progress(tmp_path):
    path = tmp_path / "old-progress.sqlite3"
    connection = sqlite3.connect(str(path))
    connection.execute("CREATE TABLE schema_info (version INTEGER NOT NULL)")
    connection.execute("INSERT INTO schema_info VALUES (1)")
    connection.execute(
        """CREATE TABLE lesson_progress (
            lesson_id TEXT PRIMARY KEY, content_revision INTEGER NOT NULL,
            step_index INTEGER NOT NULL, completed INTEGER NOT NULL,
            attempts INTEGER NOT NULL, hints_used INTEGER NOT NULL,
            reveals INTEGER NOT NULL, successes INTEGER NOT NULL,
            updated_at TEXT NOT NULL)""")
    connection.execute(
        "INSERT INTO lesson_progress VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("old-lesson", 1, 2, 1, 4, 1, 1, 2, "2026-09-23T12:00:00+00:00"))
    connection.commit()
    connection.close()
    with ProgressStore(path) as store:
        record = store.load("old-lesson", 1)
        assert record.completed and record.attempts == 4
        version = store.connection.execute(
            "SELECT version FROM schema_info").fetchone()[0]
        assert version == 5


def test_settings_round_trip_and_schema_two_migration(tmp_path):
    path = tmp_path / "settings.sqlite3"
    connection = sqlite3.connect(str(path))
    connection.execute("CREATE TABLE schema_info (version INTEGER NOT NULL)")
    connection.execute("INSERT INTO schema_info VALUES (2)")
    connection.execute(
        """CREATE TABLE lesson_progress (
            lesson_id TEXT NOT NULL, content_revision INTEGER NOT NULL,
            step_index INTEGER NOT NULL, completed INTEGER NOT NULL,
            attempts INTEGER NOT NULL, hints_used INTEGER NOT NULL,
            reveals INTEGER NOT NULL, successes INTEGER NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (lesson_id, content_revision))""")
    connection.commit()
    connection.close()

    with ProgressStore(path) as store:
        store.save_settings({
            "text_scale": 1.4,
            "board_style": "Ocean",
            "white_color": (250, 250, 250),
        })
        assert store.load_settings() == {
            "board_style": "Ocean",
            "text_scale": 1.4,
            "white_color": [250, 250, 250],
        }
        version = store.connection.execute(
            "SELECT version FROM schema_info").fetchone()[0]
        assert version == 5


def test_schema_three_migration_keeps_old_completion_unknown(tmp_path):
    path = tmp_path / "schema-three.sqlite3"
    connection = sqlite3.connect(str(path))
    connection.execute("CREATE TABLE schema_info (version INTEGER NOT NULL)")
    connection.execute("INSERT INTO schema_info VALUES (3)")
    connection.execute(
        """CREATE TABLE lesson_progress (
            lesson_id TEXT NOT NULL, content_revision INTEGER NOT NULL,
            step_index INTEGER NOT NULL, completed INTEGER NOT NULL,
            attempts INTEGER NOT NULL, hints_used INTEGER NOT NULL,
            reveals INTEGER NOT NULL, successes INTEGER NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (lesson_id, content_revision))""")
    connection.execute(
        "INSERT INTO lesson_progress VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("old-lesson", 1, 0, 1, 1, 0, 0, 1,
         "2026-09-23T12:00:00+00:00"))
    connection.execute("CREATE TABLE app_settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    connection.commit()
    connection.close()
    with ProgressStore(path) as store:
        assert store.load("old-lesson", 1).completed
        assert store.load_step_progress("old-lesson", 1) == {}
        assert store.connection.execute(
            "SELECT version FROM schema_info").fetchone()[0] == 5


def test_assistance_survives_resume_and_fresh_revisit(tmp_path):
    from chess_game.ui import ChessUI
    import pygame

    path = tmp_path / "assistance.sqlite3"
    ui = ChessUI(path)
    entry = ui.game_library.lesson_entry("olive-catalan-try-alone")
    ui.start_lesson(entry)
    ui._lesson_hint()
    ui._leave_lesson()
    ui.progress_store.close()
    pygame.quit()

    resumed = ChessUI(path)
    resumed._continue_learning()
    assert resumed.lesson.assisted
    resumed._apply_lesson_move(
        resumed.lesson.adapter.resolve_uci(resumed.board, "f1g2"))
    resumed._lesson_continue()
    assert resumed._course_entry_status(entry) == "REVISIT"
    resumed._lesson_restart()
    assert not resumed.lesson.assisted
    resumed._apply_lesson_move(
        resumed.lesson.adapter.resolve_uci(resumed.board, "f1g2"))
    resumed._lesson_continue()
    assert resumed._course_entry_status(entry) == "DONE"
    resumed.progress_store.close()
    pygame.quit()


def test_reveal_and_multi_move_help_survive_step_restart(tmp_path):
    library = load_game_library()
    path = tmp_path / "attempts.sqlite3"
    with ProgressStore(path) as store:
        for lesson_id, first_move in (
                ("olive-catalan-try-alone", None),
                ("bruno-scotch-make-room", "d2d4")):
            entry = library.lesson_entry(lesson_id)
            controller = LessonController(entry.game, entry.lesson)
            controller.begin_question()
            if first_move:
                controller.request_hint()
                controller.attempt_uci(first_move)
            else:
                controller.reveal()
            record = store.save(controller)
            resumed = LessonController(
                entry.game, entry.lesson, resume_step=record.step_index,
                resume_assisted=record.active_assisted,
                step_progress=store.load_step_progress(
                    lesson_id, entry.lesson.content_revision))
            resumed.begin_question()
            assert resumed.assisted
            resumed.begin_exploration()
            resumed.return_from_exploration()
            assert resumed.assisted
            if first_move:
                assert resumed.attempt_uci(first_move).outcome == "continue"
                assert resumed.attempt_uci("f3d4").outcome == "preferred"
            else:
                assert resumed.attempt_uci("f1g2").outcome == "preferred"
            assert resumed.step_progress[resumed.current_step.step_id]["outcome"] == "helped"


def test_schema_four_migration_conservatively_restores_help(tmp_path):
    path = tmp_path / "schema-four.sqlite3"
    connection = sqlite3.connect(str(path))
    connection.execute("CREATE TABLE schema_info (version INTEGER NOT NULL)")
    connection.execute("INSERT INTO schema_info VALUES (4)")
    connection.execute(
        """CREATE TABLE lesson_progress (
            lesson_id TEXT NOT NULL, content_revision INTEGER NOT NULL,
            step_index INTEGER NOT NULL, completed INTEGER NOT NULL,
            attempts INTEGER NOT NULL, hints_used INTEGER NOT NULL,
            reveals INTEGER NOT NULL, successes INTEGER NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (lesson_id, content_revision))""")
    connection.executemany(
        "INSERT INTO lesson_progress VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (("unfinished", 1, 0, 0, 1, 1, 0, 0, "2026-09-25"),
         ("completed", 1, 0, 1, 1, 1, 0, 1, "2026-09-25")))
    connection.commit()
    connection.close()
    with ProgressStore(path) as store:
        assert store.load("unfinished", 1).active_assisted
        assert not store.load("completed", 1).active_assisted
        assert store.load("completed", 1).successes == 1
        assert store.connection.execute(
            "SELECT version FROM schema_info").fetchone()[0] == 5


def test_transfer_step_can_be_revisited_without_hint(tmp_path):
    entry = load_game_library().lesson_entry("bruno-scotch-try-alone")
    path = tmp_path / "transfer.sqlite3"
    with ProgressStore(path) as store:
        lesson = LessonController(entry.game, entry.lesson)
        lesson.begin_question()
        lesson.request_hint()
        lesson.attempt_uci("d2d4")
        lesson.continue_lesson()
        store.save(lesson)
        step = store.load_step_progress(
            entry.lesson.lesson_id, entry.lesson.content_revision)[
            "four-knights-centre"]
        assert step.outcome == "helped" and step.hints_used == 1

        replay = LessonController(
            entry.game, entry.lesson, completed=True,
            step_progress=store.load_step_progress(
                entry.lesson.lesson_id, entry.lesson.content_revision))
        replay.restart()
        replay.begin_question()
        replay.attempt_uci("d2d4")
        replay.continue_lesson()
        store.save(replay)
        step = store.load_step_progress(
            entry.lesson.lesson_id, entry.lesson.content_revision)[
            "four-knights-centre"]
        assert step.outcome == "independent" and step.hints_used == 1


def main():
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as directory:
        globals()["tmp_path"] = Path(directory)
        test_progress_round_trip_and_update(Path(directory))
        test_completed_progress_survives_restart(Path(directory))
        test_new_content_revision_preserves_completed_history(Path(directory))
        test_schema_one_is_migrated_without_losing_progress(Path(directory))
        test_settings_round_trip_and_schema_two_migration(Path(directory))
    print("all progress tests passed")


if __name__ == "__main__":
    main()
