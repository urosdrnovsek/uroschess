"""Challenge persistence, move ownership, and earned badge checks."""

import os
import threading

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pytest

from chess_game.board import Board
from chess_game import ai
from chess_game.challenge import ChallengeStore, ROSTER, stage_states
from chess_game.difficulty import DIFFICULTIES
from chess_game.moves import legal_moves
from chess_game.notation import from_fen
from chess_game.pieces import BLACK, WHITE
from chess_game.study.progress import ProgressStore, SCHEMA_VERSION


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
    assert stage_states(victories) == ("complete",) * 5


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
            assert white.opponent.policy_parameters["seconds"] == DIFFICULTIES[
                opponent.preset][1]
            _play_authored_mate(white, (
                "e2e4", "f7f6", "d2d4", "g7g5", "d1h5"))
            assert (opponent.ident, WHITE) in store.victories()
            black = store.start(BLACK, opponent.ident)
            _play_authored_mate(black, (
                "f2f3", "e7e5", "g2g4", "d8h4"))
            assert (opponent.ident, BLACK) in store.victories()
        assert stage_states(store.victories()) == ("complete",) * 5
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
    board = Board()
    for uci in ("f2f3", "e7e5", "g2g4"):
        board.make_move(move(board, uci))
    chosen, _score, _pv, _nodes = ai.analyse(
        board, time_limit=DIFFICULTIES[0][1], max_depth=DIFFICULTIES[0][2])
    assert str(chosen) == "d8h4"
    hanging_queen = from_fen("4k3/8/8/8/8/8/4q3/4R2K w - - 0 1")
    chosen, _score, _pv, _nodes = ai.analyse(
        hanging_queen, time_limit=DIFFICULTIES[0][1],
        max_depth=DIFFICULTIES[0][2])
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


def test_engine_honours_cancellation():
    cancelled = threading.Event()
    cancelled.set()
    with pytest.raises(ai.SearchCancelled):
        ai.analyse(Board(), time_limit=6.0, cancel_event=cancelled)
