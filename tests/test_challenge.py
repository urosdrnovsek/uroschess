"""Challenge persistence, move ownership, and earned badge checks."""

import os
import json
import sqlite3
import threading

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pytest

from chess_game.board import Board
from chess_game import ai
from chess_game.challenge import (ChallengeSaveError, ChallengeStore, ROSTER,
                                  stage_states)
from chess_game.challenge_commentary import VOICES
from chess_game.chess_thoughts import THOUGHTS
from chess_game.difficulty import DIFFICULTIES
from chess_game.moves import legal_moves
from chess_game.notation import from_fen, to_fen
from chess_game.pieces import BLACK, WHITE
from chess_game.study.progress import ProgressStore, ProgressStoreError, SCHEMA_VERSION


def move(board, uci):
    return next(item for item in legal_moves(board) if str(item) == uci)


def test_stage_order_is_derived_from_victories():
    victories = set()
    for index, opponent in enumerate(ROSTER):
        assert stage_states(victories)[index] == "white_required"
        victories.add((opponent.ident, WHITE))
        assert stage_states(victories)[index] == "black_required"
        victories.add((opponent.ident, BLACK))
        assert stage_states(victories)[index] == "complete"
    assert stage_states(victories) == ("complete",) * len(ROSTER)


def test_each_character_has_distinct_short_match_and_general_lines():
    for opponent in ROSTER:
        voice = VOICES[opponent.ident]
        general = {thought.quote for thought in THOUGHTS
                   if thought.short_name == opponent.name}
        assert len(general) >= 10
        assert len(voice.after_move) == len(set(voice.after_move)) == 10
        assert not general.intersection(voice.after_move)
        assert all(0 < len(line) <= 56 for line in (
            voice.greeting, *voice.after_move, voice.character_wins,
            voice.character_loses, voice.draw))


def test_new_stages_gate_bruno_but_legacy_access_survives_upgrade(tmp_path):
    path = tmp_path / "progress.sqlite3"
    with ProgressStore(path) as progress:
        store = ChallengeStore(progress)
        chicky = store.start(WHITE)
        store.discard(chicky.match_id)
        with progress.connection:
            progress.connection.executemany(
                "INSERT INTO challenge_victories VALUES (?, ?, ?, 'now')",
                ((opponent, color, chicky.match_id)
                 for opponent in ("chicky", "pippa-pomeranian")
                 for color in (WHITE, BLACK)))
            progress.connection.execute("DROP TABLE challenge_legacy_access")
            progress.connection.execute("UPDATE schema_info SET version = 7")
    with ProgressStore(path) as upgraded:
        store = ChallengeStore(upgraded)
        states = store.stages()
        assert states[2:5] == ("white_required", "locked", "white_required")
        assert store.start(WHITE, "bruno-bear").opponent.name == "Bruno"
        assert upgraded.connection.execute(
            "SELECT version FROM schema_info").fetchone()[0] == SCHEMA_VERSION


def test_chicky_resume_preserves_history_comment_and_policy(tmp_path):
    path = tmp_path / "progress.sqlite3"
    with ProgressStore(path) as progress:
        store = ChallengeStore(progress)
        session = store.start(WHITE)
        session.accept(move(session.board, "e2e4"), WHITE)
        reply = session.choose_move()
        with pytest.raises(ValueError):
            session.accept(move(session.board, next(
                str(item) for item in legal_moves(session.board)
                if item != reply)), BLACK)
        session.accept(reply, BLACK)
        comment = session.comment
        fen = store.active()["verified_fen"]
        resumed = store.resume()
        assert resumed.comment == comment
        assert resumed.board.history == session.board.history
        assert resumed.board.zobrist == session.board.zobrist
        assert fen == store.active()["verified_fen"]
        assert resumed.moves == session.moves
        store.discard(session.match_id)
        assert store.active() is None
        assert store.victories() == set()
    with ProgressStore(path) as reopened:
        assert reopened.connection.execute(
            "SELECT version FROM schema_info").fetchone()[0] == SCHEMA_VERSION


def test_black_mate_awards_once_after_white_badge(tmp_path):
    with ProgressStore(tmp_path / "progress.sqlite3") as progress:
        store = ChallengeStore(progress)
        # Seed the prerequisite to exercise the Black result transaction.
        white = store.start(WHITE)
        store.discard(white.match_id)
        with progress.connection:
            progress.connection.execute(
                "INSERT INTO challenge_victories VALUES ('chicky', 'w', ?, 'now')",
                (white.match_id,))
        session = store.start(BLACK)
        # Find a reproducible Chicky seed that plays the two White moves in
        # Fool's mate. Black's moves remain ordinary legal human moves.
        for seed in range(30000):
            board = Board()
            first = next(item for item in legal_moves(board)
                         if str(item) == "f2f3")
            session.move_seed = seed
            session.board = board
            session.moves = []
            if session.choose_move() != first:
                continue
            board.make_move(first)
            board.make_move(move(board, "e7e5"))
            # Use the exact ply count while checking the second random choice.
            session.moves = [first, object()]
            if str(session.choose_move()) == "g2g4":
                break
        else:
            pytest.fail("No deterministic Fool's mate seed found")
        session.board = Board()
        session.moves = []
        with progress.connection:
            progress.connection.execute(
                "UPDATE challenge_matches SET move_seed = ? WHERE match_id = ?",
                (session.move_seed, session.match_id))
        session.accept(move(session.board, "f2f3"), WHITE)
        session.accept(move(session.board, "e7e5"), BLACK)
        session.accept(move(session.board, "g2g4"), WHITE)
        session.accept(move(session.board, "d8h4"), BLACK)
        assert session.status == "checkmate"
        assert ("chicky", BLACK) in store.victories()
        assert store.medal_counts()["chicky"] == 1
        assert stage_states(store.victories())[0] == "complete"
        with pytest.raises(ValueError):
            session.accept(move(Board(), "e2e4"), WHITE)
        assert progress.connection.execute(
            "SELECT COUNT(*) FROM challenge_victories WHERE opponent_id='chicky'"
        ).fetchone()[0] == 2


def _play_authored_mate(session, uci_moves):
    for uci in uci_moves:
        actor = session.board.side_to_move
        chosen = move(session.board, uci)
        if actor != session.color and session.opponent.preset is not None:
            session.authorize_search_move(chosen)
        session.accept(chosen, actor)
    assert session.status == "checkmate"


def test_search_roster_unlocks_and_master_award_once(tmp_path):
    with ProgressStore(tmp_path / "progress.sqlite3") as progress:
        store = ChallengeStore(progress)
        # Chicky's random policy is covered by its own seeded match test.
        chicky = store.start(WHITE)
        store.discard(chicky.match_id)
        with progress.connection:
            progress.connection.executemany(
                "INSERT INTO challenge_victories VALUES ('chicky', ?, ?, 'now')",
                ((WHITE, chicky.match_id), (BLACK, chicky.match_id)))
        for opponent in ROSTER[1:]:
            white = store.start(WHITE, opponent.ident)
            assert white.opponent.policy_parameters["seconds"] == (
                2.0 if opponent.ident == "olive-owl" else
                DIFFICULTIES[opponent.preset][1])
            assert white.opponent.policy_parameters["depth"] == (
                1 if opponent.ident == "pippa-pomeranian" else
                1 if opponent.ident == "tina-turtle" else
                1 if opponent.ident == "tom-rabbit" else
                2 if opponent.ident == "bruno-bear" else
                32 if opponent.ident == "olive-owl" else
                DIFFICULTIES[opponent.preset][2])
            if opponent.ident in ("tina-turtle", "tom-rabbit"):
                assert white.opponent.policy_parameters["random_move_chance"] == (
                    0.3 if opponent.ident == "tina-turtle" else 0.1)
            _play_authored_mate(white, (
                "e2e4", "f7f6", "d2d4", "g7g5", "d1h5"))
            assert (opponent.ident, WHITE) in store.victories()
            black = store.start(BLACK, opponent.ident)
            _play_authored_mate(black, (
                "f2f3", "e7e5", "g2g4", "d8h4"))
            assert (opponent.ident, BLACK) in store.victories()
        assert stage_states(store.victories()) == ("complete",) * len(ROSTER)
        award = store.award()
        assert award["match_id"] == black.match_id
        assert award["celebration_seen_at"] is None
        store.mark_celebration_seen()
        assert store.award()["celebration_seen_at"] is not None
        earned = store.award()["earned_at"]
        rematch = store.start(WHITE, ROSTER[-1].ident)
        _play_authored_mate(rematch, (
            "e2e4", "f7f6", "d2d4", "g7g5", "d1h5"))
        assert store.award()["earned_at"] == earned


def test_search_session_resumes_with_frozen_policy(tmp_path):
    with ProgressStore(tmp_path / "progress.sqlite3") as progress:
        store = ChallengeStore(progress)
        chicky = store.start(WHITE)
        store.discard(chicky.match_id)
        with progress.connection:
            progress.connection.executemany(
                "INSERT INTO challenge_victories VALUES ('chicky', ?, ?, 'now')",
                ((WHITE, chicky.match_id), (BLACK, chicky.match_id)))
        session = store.start(WHITE, "pippa-pomeranian")
        session.accept(move(session.board, "e2e4"), WHITE)
        assert store.resume().board.history == session.board.history
        with progress.connection:
            progress.connection.execute(
                "UPDATE challenge_policies SET parameters_json = '{}' WHERE match_id = ?",
                (session.match_id,))
        with pytest.raises(ValueError, match="older opponent policy"):
            store.resume()


def test_pippa_random_moves_are_seeded_and_legal(tmp_path):
    with ProgressStore(tmp_path / "progress.sqlite3") as progress:
        store = ChallengeStore(progress)
        chicky = store.start(WHITE)
        store.discard(chicky.match_id)
        with progress.connection:
            progress.connection.executemany(
                "INSERT INTO challenge_victories VALUES ('chicky', ?, ?, 'now')",
                ((WHITE, chicky.match_id), (BLACK, chicky.match_id)))
        session = store.start(WHITE, "pippa-pomeranian")
        session.accept(move(session.board, "e2e4"), WHITE)
        assert session.opponent.policy_parameters["random_move_chance"] == 0.5
        random_turns = 0
        for seed in range(200):
            session.move_seed = seed
            chosen = session.choose_random_search_move()
            assert chosen == session.choose_random_search_move()
            if chosen is not None:
                assert chosen in legal_moves(session.board)
                random_turns += 1
        assert 75 <= random_turns <= 125


def test_resignation_finishes_without_a_badge(tmp_path):
    with ProgressStore(tmp_path / "progress.sqlite3") as progress:
        store = ChallengeStore(progress)
        session = store.start(WHITE)
        session.accept(move(session.board, "e2e4"), WHITE)
        session.resign()
        assert session.status == "resignation"
        assert store.active() is None
        assert store.victories() == set()
        with pytest.raises(ValueError):
            session.resign()


def test_schema_six_chicky_save_survives_upgrade(tmp_path):
    path = tmp_path / "progress.sqlite3"
    with ProgressStore(path) as progress:
        store = ChallengeStore(progress)
        session = store.start(WHITE)
        session.accept(move(session.board, "e2e4"), WHITE)
        with progress.connection:
            progress.connection.execute(
                "DELETE FROM challenge_policies WHERE match_id = ?",
                (session.match_id,))
            progress.connection.execute("DROP TABLE challenge_awards")
            progress.connection.execute("DROP TABLE challenge_policies")
            progress.connection.execute("UPDATE schema_info SET version = 6")
    with ProgressStore(path) as upgraded:
        restored = ChallengeStore(upgraded).resume()
        assert restored.match_id == session.match_id
        assert restored.board.history == session.board.history
        assert upgraded.connection.execute(
            "SELECT version FROM schema_info").fetchone()[0] == SCHEMA_VERSION


def test_pippa_finds_mate_and_monty_uses_max_preset():
    pippa = ROSTER[1].policy_parameters
    board = Board()
    for uci in ("f2f3", "e7e5", "g2g4"):
        board.make_move(move(board, uci))
    chosen, _score, _pv, _nodes = ai.analyse(
        board, time_limit=pippa["seconds"], max_depth=pippa["depth"])
    assert str(chosen) == "d8h4"
    hanging_queen = from_fen("4k3/8/8/8/8/8/4q3/4R2K w - - 0 1")
    chosen, _score, _pv, _nodes = ai.analyse(
        hanging_queen, time_limit=pippa["seconds"],
        max_depth=pippa["depth"])
    assert str(chosen) == "e1e2"
    assert ROSTER[-1].policy_parameters == {
        "kind": "search", "preset": "Max", "seconds": 6.0,
        "depth": 64, "revision": 1,
    }


def test_navigation_cancels_search_and_preserves_match(tmp_path, monkeypatch):
    from chess_game.ui import ChessUI

    entered = threading.Event()
    cancelled = threading.Event()

    def searching(_board, **kwargs):
        entered.set()
        assert kwargs["cancel_event"].wait(2)
        cancelled.set()
        raise ai.SearchCancelled

    monkeypatch.setattr(ai, "analyse", searching)
    monkeypatch.setattr(
        "chess_game.challenge.ChallengeSession.choose_random_search_move",
        lambda self: None)
    ui = ChessUI(tmp_path / "progress.sqlite3")
    try:
        chicky = ui.challenge_store.start(WHITE)
        ui.challenge_store.discard(chicky.match_id)
        with ui.progress_store.connection:
            ui.progress_store.connection.executemany(
                "INSERT INTO challenge_victories VALUES ('chicky', ?, ?, 'now')",
                ((WHITE, chicky.match_id), (BLACK, chicky.match_id)))
            ui.progress_store.connection.execute(
                "INSERT INTO challenge_victories VALUES ('pippa-pomeranian', 'w', ?, 'now')",
                (chicky.match_id,))
        ui._start_challenge(BLACK, "pippa-pomeranian")
        assert entered.wait(2)
        match_id = ui.challenge.match_id
        ui._to_menu()
        assert cancelled.wait(2)
        assert ui.challenge_store.active()["match_id"] == match_id
        assert ui.challenge_store.active()["moves_json"] == "[]"
    finally:
        ui.progress_store.close()
        import pygame
        pygame.quit()


def test_seven_character_roster_is_reachable_at_small_sizes(tmp_path):
    from chess_game.ui import ChessUI
    import pygame

    ui = ChessUI(tmp_path / "progress.sqlite3")
    try:
        ui._open_challenge_menu()
        for width, height in ((360, 700), (600, 600), (980, 760)):
            ui._on_resize(width, height)
            for scale in (1.0, 1.2, 1.4):
                ui._set_text_scale(scale)
                for page in (0, 1):
                    ui.challenge_page = page
                    ui._menu_buttons = []
                    ui._draw()
                    cards = [button for button in ui._menu_buttons
                             if button.kind == "challenge"]
                    assert len(cards) == (4 if page == 0 else 3)
                    assert all(ui.screen.get_rect().contains(button.rect)
                               for button in ui._menu_buttons)
                    if page == 0:
                        assert [card.label.split(" · ")[0] for card in cards] == [
                            "Chicky", "Pippa", "Tina", "Tom"]
                    else:
                        assert [card.label.split(" · ")[0] for card in cards] == [
                            "Bruno", "Olivia", "Monty"]
        ui._on_key(pygame.K_PAGEUP)
        assert ui.challenge_page == 0
        ui._on_key(pygame.K_PAGEDOWN)
        assert ui.challenge_page == 1
    finally:
        ui.progress_store.close()
        pygame.quit()


def test_engine_honours_cancellation():
    cancelled = threading.Event()
    cancelled.set()
    with pytest.raises(ai.SearchCancelled):
        ai.analyse(Board(), time_limit=6.0, cancel_event=cancelled)


@pytest.mark.parametrize("column,value,reason", (
    ("moves_json", "{", "malformed_history"),
    ("moves_json", json.dumps({"move": "e2e4"}), "malformed_history"),
    ("moves_json", json.dumps(["e2e5"]), "invalid_history"),
    ("verified_fen", "incorrect", "position_mismatch"),
    ("comment_id", "9", "invalid_commentary"),
    ("opponent_id", "missing-opponent", "unsupported_opponent"),
    ("policy_revision", 99, "unsupported_policy"),
))
def test_invalid_save_is_read_only_and_archives_without_rewards(
        tmp_path, column, value, reason):
    path = tmp_path / "progress.sqlite3"
    with ProgressStore(path) as progress:
        store = ChallengeStore(progress)
        session = store.start(WHITE)
        with progress.connection:
            progress.connection.execute(
                "UPDATE challenge_matches SET {} = ? WHERE match_id = ?".format(column),
                (value, session.match_id))
        original = dict(store.active())
        checked = store.inspect_active()
        assert checked.reason == reason and checked.session is None
        assert dict(store.active()) == original
        with pytest.raises(ChallengeSaveError) as error:
            store.resume()
        assert error.value.result.reason == reason
        export_path = tmp_path / "saved-match.json"
        store.export_match(session.match_id, export_path)
        assert json.loads(export_path.read_text())["match"] == original
        archived = store.archive_invalid(session.match_id)
        assert archived.reason == reason
        assert store.active() is None
        assert store.victories() == set()
        kept = progress.connection.execute(
            "SELECT * FROM challenge_matches WHERE match_id = ?",
            (session.match_id,)).fetchone()
        assert kept["moves_json"] == original["moves_json"]
        assert kept["verified_fen"] == original["verified_fen"]
        assert kept["state"] == "abandoned"
        recovery = progress.connection.execute(
            "SELECT * FROM challenge_recovery WHERE match_id = ?",
            (session.match_id,)).fetchone()
        assert recovery["reason_code"] == reason
        archived_export = tmp_path / "archived-match.json"
        store.export_match(session.match_id, archived_export)
        assert json.loads(archived_export.read_text())["original_match"] == original
        with pytest.raises(ValueError, match="no longer active"):
            store.archive_invalid(session.match_id)
    with ProgressStore(path) as reopened:
        assert ChallengeStore(reopened).active() is None
        assert reopened.connection.execute(
            "SELECT reason_code FROM challenge_recovery WHERE match_id = ?",
            (session.match_id,)).fetchone()[0] == reason


def test_recovery_archive_rolls_back_when_match_update_fails(tmp_path):
    with ProgressStore(tmp_path / "progress.sqlite3") as progress:
        store = ChallengeStore(progress)
        session = store.start(WHITE)
        with progress.connection:
            progress.connection.execute(
                "UPDATE challenge_matches SET moves_json = '{' WHERE match_id = ?",
                (session.match_id,))
            progress.connection.execute(
                """CREATE TRIGGER reject_archive BEFORE UPDATE ON challenge_matches
                   BEGIN SELECT RAISE(ABORT, 'write failed'); END""")
        with pytest.raises(sqlite3.IntegrityError, match="write failed"):
            store.archive_invalid(session.match_id)
        assert store.active()["match_id"] == session.match_id
        assert progress.connection.execute(
            "SELECT COUNT(*) FROM challenge_recovery").fetchone()[0] == 0
        with progress.connection:
            progress.connection.execute("DROP TRIGGER reject_archive")
        store.archive_invalid(session.match_id)
        assert store.active() is None


def test_failed_checkmate_transaction_keeps_committed_position_and_no_badge(tmp_path):
    with ProgressStore(tmp_path / "progress.sqlite3") as progress:
        store = ChallengeStore(progress)
        chicky = store.start(WHITE)
        store.discard(chicky.match_id)
        with progress.connection:
            progress.connection.executemany(
                "INSERT INTO challenge_victories VALUES ('chicky', ?, ?, 'now')",
                ((WHITE, chicky.match_id), (BLACK, chicky.match_id)))
        session = store.start(WHITE, "pippa-pomeranian")
        for uci in ("e2e4", "f7f6", "d2d4", "g7g5"):
            chosen = move(session.board, uci)
            if session.board.side_to_move == BLACK:
                session.authorize_search_move(chosen)
            session.accept(chosen, session.board.side_to_move)
        committed_fen = to_fen(session.board)
        with progress.connection:
            progress.connection.execute(
                """CREATE TRIGGER reject_badge BEFORE INSERT ON challenge_victories
                   BEGIN SELECT RAISE(ABORT, 'badge write failed'); END""")
        with pytest.raises(sqlite3.IntegrityError, match="badge write failed"):
            session.accept(move(session.board, "d1h5"), WHITE)
        assert to_fen(session.board) == committed_fen
        assert session.status == "ongoing"
        assert store.active()["verified_fen"] == committed_fen
        assert (session.opponent.ident, WHITE) not in store.victories()
        assert store.medal_counts()[session.opponent.ident] == 0
        with progress.connection:
            progress.connection.execute("DROP TRIGGER reject_badge")
        session.accept(move(session.board, "d1h5"), WHITE)
        assert session.status == "checkmate"
        assert (session.opponent.ident, WHITE) in store.victories()
        assert store.medal_counts()[session.opponent.ident] == 1


def test_saved_policy_mismatch_preserves_original_record(tmp_path):
    with ProgressStore(tmp_path / "progress.sqlite3") as progress:
        store = ChallengeStore(progress)
        chicky = store.start(WHITE)
        store.discard(chicky.match_id)
        with progress.connection:
            progress.connection.executemany(
                "INSERT INTO challenge_victories VALUES ('chicky', ?, ?, 'now')",
                ((WHITE, chicky.match_id), (BLACK, chicky.match_id)))
        session = store.start(WHITE, "pippa-pomeranian")
        with progress.connection:
            progress.connection.execute(
                "UPDATE challenge_policies SET parameters_json = '{}' WHERE match_id = ?",
                (session.match_id,))
        assert store.inspect_active().reason == "unsupported_policy"
        store.archive_invalid(session.match_id)
        assert progress.connection.execute(
            "SELECT parameters_json FROM challenge_policies WHERE match_id = ?",
            (session.match_id,)).fetchone()[0] == "{}"


def test_valid_black_save_keeps_board_and_comment(tmp_path):
    with ProgressStore(tmp_path / "progress.sqlite3") as progress:
        store = ChallengeStore(progress)
        chicky = store.start(WHITE)
        store.discard(chicky.match_id)
        with progress.connection:
            progress.connection.executemany(
                "INSERT INTO challenge_victories VALUES ('chicky', ?, ?, 'now')",
                ((WHITE, chicky.match_id), (BLACK, chicky.match_id)))
            progress.connection.execute(
                "INSERT INTO challenge_victories VALUES ('pippa-pomeranian', 'w', ?, 'now')",
                (chicky.match_id,))
        session = store.start(BLACK, "pippa-pomeranian")
        first = move(session.board, "e2e4")
        session.authorize_search_move(first)
        session.accept(first, WHITE)
        session.accept(move(session.board, "e7e5"), BLACK)
        response = move(session.board, "g1f3")
        session.authorize_search_move(response)
        session.accept(response, WHITE)
        checked = store.inspect_active()
        assert checked.valid
        assert checked.session.comment == session.comment
        assert checked.session.board.history == session.board.history


def test_recovery_ui_exports_and_archives_saved_match(tmp_path):
    from chess_game.ui import ChessUI
    import pygame

    ui = ChessUI(tmp_path / "progress.sqlite3")
    try:
        session = ui.challenge_store.start(WHITE)
        with ui.progress_store.connection:
            ui.progress_store.connection.execute(
                "UPDATE challenge_matches SET moves_json = '{' WHERE match_id = ?",
                (session.match_id,))
        ui._open_challenge_menu()
        assert ui.menu_view == "challenge_recovery"
        ui._build_menu_buttons()
        assert [button.label for button in ui._menu_buttons] == [
            "Retry saved match", "Export saved match",
            "Archive and start again", "Back to Play"]
        ui._export_challenge_recovery()
        exported = list(tmp_path.glob("recovery-*.json"))
        assert len(exported) == 1
        assert json.loads(exported[0].read_text())["match"]["match_id"] == session.match_id
        ui._archive_challenge_recovery()
        assert ui.menu_view == "challenge"
        assert ui.challenge_store.active() is None
        ui._open_challenge_archive()
        assert ui.menu_view == "challenge_archive"
        ui._build_menu_buttons()
        assert "Export saved match" in [button.label for button in ui._menu_buttons]
        for width, height in ((360, 700), (600, 600), (980, 760)):
            ui._on_resize(width, height)
            for scale in (1.0, 1.2, 1.4):
                ui._set_text_scale(scale)
                ui._build_menu_buttons()
                assert all(ui.screen.get_rect().contains(button.rect)
                           for button in ui._menu_buttons)
        ui._export_challenge_recovery()
        archived_export = next(
            path for path in tmp_path.glob("recovery-*.json")
            if json.loads(path.read_text())["recovery"] is not None)
        assert json.loads(archived_export.read_text())["recovery"][
            "reason_code"] == "malformed_history"
    finally:
        ui.progress_store.close()
        pygame.quit()
    reopened = ChessUI(tmp_path / "progress.sqlite3")
    try:
        reopened._open_challenge_archive()
        assert reopened.menu_view == "challenge_archive"
        assert reopened.recovery_result.match_id == session.match_id
    finally:
        reopened.progress_store.close()
        pygame.quit()


def test_database_read_error_offers_retry_without_archiving(tmp_path, monkeypatch):
    from chess_game.ui import ChessUI
    import pygame

    ui = ChessUI(tmp_path / "progress.sqlite3")
    original = ui.challenge_store.inspect_active

    def failed_read():
        raise sqlite3.OperationalError("temporarily unavailable")

    try:
        session = ui.challenge_store.start(WHITE)
        monkeypatch.setattr(ui.challenge_store, "inspect_active", failed_read)
        ui._open_challenge_menu()
        assert ui.menu_view == "challenge_unavailable"
        ui._build_menu_buttons()
        assert [button.label for button in ui._menu_buttons] == [
            "Retry", "Back to Play"]
        assert ui.challenge_store.active()["match_id"] == session.match_id
        assert ui.challenge_store.victories() == set()
        monkeypatch.setattr(ui.challenge_store, "inspect_active", original)
        ui._open_challenge_menu()
        assert ui.menu_view == "challenge"
    finally:
        ui.progress_store.close()
        pygame.quit()


def test_failed_move_save_freezes_until_explicit_retry(tmp_path, monkeypatch):
    from chess_game.ui import ChessUI
    import pygame

    ui = ChessUI(tmp_path / "progress.sqlite3")
    try:
        ui._start_challenge(WHITE)
        session = ui.challenge
        initial_fen = to_fen(session.board)
        chosen = move(session.board, "e2e4")
        original_save = ui.challenge_store._save
        calls = {"count": 0}

        def fail_once(*args, **kwargs):
            calls["count"] += 1
            if calls["count"] == 1:
                raise sqlite3.OperationalError("disk busy")
            return original_save(*args, **kwargs)

        monkeypatch.setattr(ui.challenge_store, "_save", fail_once)
        ui._apply(chosen)
        assert to_fen(session.board) == initial_fen
        assert ui.challenge_store.active()["moves_json"] == "[]"
        assert not ui._can_move_now()
        ui._build_game_buttons()
        assert [button.label for button in ui._game_buttons] == [
            "Retry move save", "Save & return"]
        ui._retry_challenge_save()
        assert ui.challenge_save_error is None
        assert ui.challenge_store.active()["moves_json"] == '["e2e4"]'
    finally:
        ui.progress_store.close()
        pygame.quit()


def test_failed_resignation_save_freezes_until_retry(tmp_path, monkeypatch):
    from chess_game.ui import ChessUI
    import pygame

    ui = ChessUI(tmp_path / "progress.sqlite3")
    try:
        ui._start_challenge(WHITE)
        match_id = ui.challenge.match_id
        original_save = ui.challenge_store._save
        failed = {"once": False}

        def fail_once(session, result=None):
            if result == "resignation" and not failed["once"]:
                failed["once"] = True
                raise sqlite3.OperationalError("disk busy")
            return original_save(session, result)

        monkeypatch.setattr(ui.challenge_store, "_save", fail_once)
        ui._resign_challenge()
        ui._resign_challenge()
        assert ui.challenge_save_error == (None, None)
        assert ui.challenge.status == "ongoing"
        assert ui.challenge_store.active()["match_id"] == match_id
        ui._build_game_buttons()
        assert ui._game_buttons[0].label == "Retry resignation"
        ui._retry_challenge_save()
        assert ui.challenge_save_error is None
        assert ui.challenge.status == "resignation"
        assert ui.challenge_store.active() is None
        assert ui.challenge_store.victories() == set()
    finally:
        ui.progress_store.close()
        pygame.quit()


def test_recovery_schema_upgrade_rolls_back_and_can_retry(tmp_path):
    path = tmp_path / "progress.sqlite3"
    with ProgressStore(path) as progress:
        with progress.connection:
            progress.connection.execute("DROP TABLE challenge_recovery")
            progress.connection.execute("UPDATE schema_info SET version = 8")
            progress.connection.execute(
                """CREATE TRIGGER reject_version BEFORE UPDATE ON schema_info
                   BEGIN SELECT RAISE(ABORT, 'migration failed'); END""")
    with pytest.raises(ProgressStoreError, match="migration failed"):
        ProgressStore(path)
    connection = sqlite3.connect(str(path))
    assert connection.execute("SELECT version FROM schema_info").fetchone()[0] == 8
    assert connection.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE name = 'challenge_recovery'"
    ).fetchone()[0] == 0
    connection.execute("DROP TRIGGER reject_version")
    connection.commit()
    connection.close()
    with ProgressStore(path) as upgraded:
        assert upgraded.connection.execute(
            "SELECT version FROM schema_info").fetchone()[0] == SCHEMA_VERSION
        assert upgraded.connection.execute(
            "SELECT COUNT(*) FROM challenge_recovery").fetchone()[0] == 0


def test_newer_progress_schema_is_left_untouched(tmp_path):
    path = tmp_path / "progress.sqlite3"
    with ProgressStore(path) as progress:
        with progress.connection:
            progress.connection.execute("UPDATE schema_info SET version = 999")
    with pytest.raises(ProgressStoreError, match="not supported"):
        ProgressStore(path)
    connection = sqlite3.connect(str(path))
    assert connection.execute("SELECT version FROM schema_info").fetchone()[0] == 999
    connection.close()


def test_challenge_drawing_uses_refreshed_progress_snapshot(tmp_path, monkeypatch):
    from chess_game.ui import ChessUI
    import pygame

    ui = ChessUI(tmp_path / "progress.sqlite3")

    def unexpected_read():
        raise AssertionError("drawing must use the cached challenge summary")

    try:
        ui._start_challenge(WHITE)
        monkeypatch.setattr(ui.challenge_store, "victories", unexpected_read)
        monkeypatch.setattr(ui.challenge_store, "stages", unexpected_read)
        monkeypatch.setattr(ui.challenge_store, "award", unexpected_read)
        ui._build_game_buttons()
        ui._draw()
        monkeypatch.undo()
        ui._open_challenge_menu()
        monkeypatch.setattr(ui.challenge_store, "active", unexpected_read)
        monkeypatch.setattr(ui.challenge_store, "stages", unexpected_read)
        monkeypatch.setattr(ui.challenge_store, "award", unexpected_read)
        ui._draw()
    finally:
        ui.progress_store.close()
        pygame.quit()
