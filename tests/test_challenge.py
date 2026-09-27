"""Challenge persistence, move ownership, and earned badge checks."""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pytest

from chess_game.board import Board
from chess_game.challenge import ChallengeStore, ROSTER, stage_states
from chess_game.moves import legal_moves
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
