"""Only verified match facts may become post-game coaching."""
from types import SimpleNamespace

import pytest

from chess_game.board import Board
from chess_game.challenge import OPPONENTS
from chess_game.study.chess_adapter import ChessAdapter
from chess_game.study.match_review import review_match
from chess_game.study.replay import ReplayController


def session(line, color='w', status='checkmate'):
    board, moves, _ = ChessAdapter.replay(line)
    return SimpleNamespace(board=board, moves=moves, color=color, status=status,
                           opponent=OPPONENTS['chicky'], match_id='test-match')


def test_review_verifies_mate_and_links_to_king_safety():
    match = session(('f2f3', 'e7e5', 'g2g4', 'd8h4'))
    original = match.board.clone()
    review = review_match(match)
    assert len(review.moments) == 1
    assert review.moments[0].ply == 4
    assert 'Chicky delivered checkmate with Qh4#' in review.moments[0].explanation
    assert review.practice_id == 'chicky-king-safety'
    replay = ReplayController(review.entry.game)
    replay.go_last()
    assert vars(replay.board) == vars(original)
    assert vars(match.board) == vars(original)


def test_review_refuses_invalid_history_position_and_result():
    match = session(('f2f3', 'e7e5', 'g2g4', 'd8h4'))
    match.board = Board()
    with pytest.raises(ValueError, match='position'):
        review_match(match)
    match = session(('e2e4',), status='checkmate')
    with pytest.raises(ValueError, match='result'):
        review_match(match)
    match = session(('e2e4',), status='ongoing')
    with pytest.raises(ValueError, match='Finish'):
        review_match(match)


def test_resignation_review_explains_only_observed_check_evasion():
    match = session(('e2e4', 'e7e5', 'd1h5', 'b8c6', 'h5e5', 'd8e7'),
                    color='b', status='resignation')
    review = review_match(match)
    assert len(review.moments) == 1
    assert 'You answered check with Qe7' in review.moments[0].explanation
    assert 'resignation' in review.entry.game.root.comment
    assert 'checkmate' not in review.moments[0].explanation


def test_empty_resigned_match_has_a_safe_review_and_practice_route():
    review = review_match(session((), status='resignation'))
    assert not review.moments
    assert not review.entry.game.root.children
    assert review.practice_id == 'chicky-king-safety'
