"""Play the new courses and verify the board claims in their feedback."""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
import pytest

from chess_game.moves import game_status, in_check, is_square_attacked
from chess_game.study import (
    COMPLETED, ChessAdapter, LessonController, ProgressStore, load_game_library,
)
from chess_game.ui import ChessUI


@pytest.fixture(scope="module")
def library():
    result = load_game_library()
    assert not result.errors
    return result


LESSONS = {
    "chicky-capture-check": ("c2e4", "e1f2"),
    "chicky-block-check": ("c1e3", "g2e3"),
    "pippa-castle-white": ("e1g1", "d2d3"),
    "pippa-castle-black": ("f8e7", "e8g8"),
    "olivia-rook-skewer": ("a1d1", "d1d8"),
    "olivia-back-rank-mate": ("e2c3", "e1e8"),
    "chicky-en-passant": ("e5d6", "d6d7"),
    "chicky-black-promotion": ("h3h2", "h2h1q"),
    "tom-remove-attacker": ("e4d5", "b1c3"),
    "tom-save-threatened-pieces": ("d2f3", "a1a2"),
    "tina-catch-a-pawn": ("f3g4", "g4h3"),
    "tina-rook-behind-pawn": ("b1a1", "a5a6"),
    "bruno-rook-seventh": ("a1a7", "a7b7"),
    "bruno-double-rooks": ("a1d1", "d2d7"),
}


@pytest.mark.parametrize("ident", LESSONS)
def test_new_lesson_can_be_completed_and_resumed(library, ident):
    entry = library.lesson_entry(ident)
    lesson = LessonController(entry.game, entry.lesson)
    first, final = LESSONS[ident]
    lesson.begin_question()
    lesson.request_hint()
    assert lesson.attempt_uci(first).outcome == "preferred"
    assert lesson.continue_lesson()
    assert lesson.current_step.practice_mode == "independent"
    with ProgressStore(":memory:") as store:
        store.save(lesson)
        record = store.load(ident, 1)
        resumed = LessonController(entry.game, entry.lesson, resume_step=record.step_index,
                                   step_progress=store.load_step_progress(ident, 1))
        resumed.begin_question()
        assert not resumed.visible_highlights and not resumed.visible_arrows
        assert resumed.attempt_uci(final).outcome == "preferred"
        assert not resumed.continue_lesson()
        assert resumed.state == COMPLETED
        store.save(resumed)
        progress = store.load_step_progress(ident, 1)
        assert progress[entry.lesson.steps[0].step_id].outcome == "helped"
        assert progress[entry.lesson.steps[1].step_id].outcome == "independent"


def controller(library, ident, step=0):
    entry = library.lesson_entry(ident)
    lesson = LessonController(entry.game, entry.lesson, resume_step=step)
    lesson.begin_question()
    return lesson


def test_check_lessons_actually_stop_checks_and_win_the_rook(library):
    capture = controller(library, "chicky-capture-check")
    assert in_check(capture.board, "w")
    capture.attempt_uci("c2e4")
    assert not in_check(capture.board, "w")
    assert capture.board.piece_at((4, 4)) == "wb"
    for move in ("e1d2", "e1e2", "e1f2"):
        escape = controller(library, "chicky-capture-check", 1)
        assert in_check(escape.board, "w")
        assert escape.attempt_uci(move).outcome in ("preferred", "acceptable")
        assert not in_check(escape.board, "w")

    block = controller(library, "chicky-block-check")
    assert in_check(block.board, "w")
    block.attempt_uci("c1e3")
    assert not in_check(block.board, "w")
    recapture = controller(library, "chicky-block-check", 1)
    assert in_check(recapture.board, "w")
    recapture.attempt_uci("g2e3")
    assert not in_check(recapture.board, "w")
    assert recapture.board.piece_at((5, 4)) == "wn"
    assert not any(piece == "br" for row in recapture.board.grid for piece in row)


def test_castling_moves_both_pieces_for_both_colours(library):
    for ident, step, move, row, color in (
        ("pippa-castle-white", 0, "e1g1", 7, "w"),
        ("pippa-castle-black", 1, "e8g8", 0, "b"),
    ):
        lesson = controller(library, ident, step)
        lesson.attempt_uci(move)
        assert lesson.board.piece_at((row, 6)) == color + "k"
        assert lesson.board.piece_at((row, 5)) == color + "r"
        assert not lesson.board.piece_at((row, 4))
        assert not lesson.board.piece_at((row, 7))


def test_rook_tactics_feedback_matches_actual_captures_and_mate(library):
    skewer = controller(library, "olivia-rook-skewer")
    original = ChessAdapter.fen(skewer.board)
    assert skewer.attempt_uci("a1a5").outcome == "wrong"
    assert ChessAdapter.fen(skewer.board) == original
    hypothetical = ChessAdapter.from_fen(original)
    ChessAdapter.apply_uci(hypothetical, "a1a5")
    assert in_check(hypothetical, "b")
    ChessAdapter.apply_uci(hypothetical, "d8a5")
    assert hypothetical.piece_at((3, 0)) == "bq"
    skewer.retry()
    skewer.attempt_uci("a1d1")
    assert in_check(skewer.board, "b")
    queen = controller(library, "olivia-rook-skewer", 1)
    queen.attempt_uci("d1d8")
    assert queen.board.piece_at((0, 3)) == "wr"
    assert not any(piece == "bq" for row in queen.board.grid for piece in row)

    mate = controller(library, "olivia-back-rank-mate", 1)
    assert mate.attempt_uci("e1e7").outcome == "wrong"
    assert game_status(mate.board) == "ongoing"
    mate.retry()
    mate.attempt_uci("e1e8")
    assert game_status(mate.board) == "checkmate"


def test_new_courses_are_reachable_and_render_at_small_window_sizes():
    ui = ChessUI(":memory:")
    try:
        for course_id in ("chicky-answer-check", "pippa-castle-both-colours", "olivia-rook-tactics",
                          "chicky-pawn-surprises", "tom-keep-pieces-safe", "tina-endgame-helpers",
                          "bruno-active-rooks"):
            course = ui.game_library.course(course_id)
            assert course in ui._guide_entries(course.player_id)
            for entry in ui.game_library.course_lessons(course):
                ui.start_lesson(entry, course_id=course_id)
                for scale in (1.0, 1.4):
                    ui._set_text_scale(scale)
                    for size in ((360, 700), (980, 760)):
                        ui._on_resize(*size)
                        ui._build_lesson_buttons()
                        ui._draw()
                        assert all(ui.screen.get_rect().contains(button.rect)
                                   for button in ui._game_buttons)
    finally:
        ui.progress_store.close()
        pygame.quit()


def test_en_passant_matches_double_step_and_expires_after_another_move(library):
    lesson = controller(library, "chicky-en-passant")
    prior = ChessAdapter.from_fen("7k/3p4/8/4P3/8/8/8/7K b - - 0 1")
    ChessAdapter.apply_uci(prior, "d7d5")
    assert ChessAdapter.fen(prior) == ChessAdapter.fen(lesson.board)
    original = ChessAdapter.fen(lesson.board)
    assert lesson.attempt_uci("h1g1").outcome == "off_goal"
    assert ChessAdapter.fen(lesson.board) == original
    delayed = ChessAdapter.from_fen(original)
    ChessAdapter.apply_uci(delayed, "h1g1")
    ChessAdapter.apply_uci(delayed, "h8g8")
    assert "e5d6" not in {str(move) for move in ChessAdapter.legal_moves(delayed)}
    lesson.retry()
    assert lesson.attempt_uci("e5d6").outcome == "preferred"
    assert lesson.board.piece_at((2, 3)) == "wp"
    assert not lesson.board.piece_at((3, 3))
    assert not lesson.board.piece_at((3, 4))


def test_black_promotion_makes_a_queen_and_checks_white(library):
    lesson = controller(library, "chicky-black-promotion", 1)
    original = ChessAdapter.fen(lesson.board)
    assert lesson.attempt_uci("h2h1r").outcome == "off_goal"
    assert ChessAdapter.fen(lesson.board) == original
    lesson.retry()
    lesson.attempt_uci("h2h1q")
    assert lesson.board.piece_at((7, 7)) == "bq"
    assert not lesson.board.piece_at((6, 7))
    assert in_check(lesson.board, "w")


def test_tom_removes_the_bishop_attacker_and_adds_a_pawn_defender(library):
    lesson = controller(library, "tom-remove-attacker")
    assert is_square_attacked(lesson.board, (4, 2), "b")
    lesson.attempt_uci("e4d5")
    assert not is_square_attacked(lesson.board, (4, 2), "b")
    assert lesson.board.piece_at((3, 3)) == "wp"
    defend = controller(library, "tom-remove-attacker", 1)
    assert is_square_attacked(defend.board, (3, 3), "b")
    # Isolate the knight's contribution: the bishop and queen already defend d5.
    without_other_defenders = defend.board
    without_other_defenders.grid[4][2] = ""
    without_other_defenders.grid[7][3] = ""
    assert not is_square_attacked(without_other_defenders, (3, 3), "w")
    defend.attempt_uci("b1c3")
    without_other_defenders = defend.board
    without_other_defenders.grid[4][2] = ""
    without_other_defenders.grid[7][3] = ""
    assert is_square_attacked(without_other_defenders, (3, 3), "w")


def test_every_reviewed_rook_escape_reaches_a_safe_square(library):
    entry = library.lesson_entry("tom-save-threatened-pieces")
    first = controller(library, "tom-save-threatened-pieces")
    assert is_square_attacked(first.board, (6, 3), "b")
    first.attempt_uci("d2f3")
    assert not is_square_attacked(first.board, (5, 5), "b")
    final = controller(library, "tom-save-threatened-pieces", 1)
    assert is_square_attacked(final.board, (7, 0), "b")
    rook_moves = {str(move) for move in ChessAdapter.legal_moves(final.board)
                  if move.frm == (7, 0)}
    accepted = {node.uci for node in entry.lesson.steps[1].question.tree
                if node.outcome in ("preferred", "acceptable")}
    assert accepted == rook_moves
    for uci in accepted:
        attempt = controller(library, "tom-save-threatened-pieces", 1)
        result = attempt.attempt_uci(uci)
        assert result.outcome in ("preferred", "acceptable")
        assert not is_square_attacked(attempt.board, result.move.to, "b")
    for step, mistake, capture in ((0, "a1a2", "h6d2"), (1, "f3g5", "g7a1")):
        attempt = controller(library, "tom-save-threatened-pieces", step)
        board = attempt.board
        assert attempt.attempt_uci(mistake).outcome == "wrong"
        ChessAdapter.apply_uci(board, mistake)
        ChessAdapter.apply_uci(board, capture)


def test_king_avoids_pawn_attack_then_captures_into_a_draw(library):
    lesson = controller(library, "tina-catch-a-pawn")
    original = ChessAdapter.fen(lesson.board)
    assert lesson.attempt_uci("f3g3").outcome == "illegal"
    assert ChessAdapter.fen(lesson.board) == original
    lesson.attempt_uci("f3g4")
    assert not in_check(lesson.board, "w")
    capture = controller(library, "tina-catch-a-pawn", 1)
    capture.attempt_uci("g4h3")
    assert game_status(capture.board) == "draw-material"
    assert library.lesson_entry("tina-catch-a-pawn").game.result == "1/2-1/2"


def test_rook_supports_passed_pawn_before_and_after_advance(library):
    lesson = controller(library, "tina-rook-behind-pawn")
    lesson.attempt_uci("b1a1")
    assert is_square_attacked(lesson.board, (3, 0), "w")
    advance = controller(library, "tina-rook-behind-pawn", 1)
    advance.attempt_uci("a5a6")
    assert advance.board.piece_at((2, 0)) == "wp"
    assert is_square_attacked(advance.board, (2, 0), "w")


def test_seventh_rank_entry_is_safe_and_eighth_rank_entry_loses_rook(library):
    lesson = controller(library, "bruno-rook-seventh")
    hypothetical = lesson.board
    ChessAdapter.apply_uci(hypothetical, "a1a8")
    assert not in_check(hypothetical, "b")
    ChessAdapter.apply_uci(hypothetical, "e8a8")
    assert hypothetical.piece_at((0, 0)) == "br"
    assert lesson.attempt_uci("a1a8").outcome == "wrong"
    lesson.retry()
    lesson.attempt_uci("a1a7")
    assert not is_square_attacked(lesson.board, (1, 0), "b")
    capture = controller(library, "bruno-rook-seventh", 1)
    assert not is_square_attacked(capture.board, (1, 1), "b")
    capture.attempt_uci("a7b7")
    assert capture.board.piece_at((1, 1)) == "wr"


def test_doubled_rooks_support_the_seventh_rank_check(library):
    lesson = controller(library, "bruno-double-rooks")
    lesson.attempt_uci("a1d1")
    assert lesson.board.piece_at((7, 3)) == "wr"
    assert lesson.board.piece_at((6, 3)) == "wr"
    assert is_square_attacked(lesson.board, (6, 3), "w")
    advance = controller(library, "bruno-double-rooks", 1)
    advance.attempt_uci("d2d7")
    assert in_check(advance.board, "b")
    assert is_square_attacked(advance.board, (1, 3), "w")
