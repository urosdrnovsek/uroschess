"""Guided-lesson validation, state, and rendering checks."""

from dataclasses import replace
from copy import deepcopy
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from chess_game.study import (
    COMPLETED,
    ContentLoadError,
    EXPLORING,
    FEEDBACK,
    QUESTION,
    READING,
    LessonController,
    LessonValidationError,
    ProgressStore,
    load_game_library,
    parse_lesson_data,
    resolve_lesson,
)
from chess_game.views import BoardView


def _entry():
    library = load_game_library()
    assert not library.errors
    return next(entry for entry in library.entries
                if entry.game.game_id == "coordination-study")


def _tree_lesson_data(entry):
    step = entry.lesson.steps[0]
    return {
        "schema_version": 2,
        "lesson_id": "two-move-development",
        "content_revision": 1,
        "title": "Develop and castle",
        "level": "beginner",
        "estimated_minutes": 5,
        "objective": "Complete a short development plan.",
        "game_id": entry.game.game_id,
        "steps": [{
            "step_id": "develop-then-castle",
            "node_path": list(step.node_path),
            "expected_fen": step.expected_fen,
            "explanation": "Develop the bishop, then make the king safe.",
            "question": {
                "kind": "move",
                "timing": "before_move",
                "evaluator": "reviewed_tree",
                "prompt": "Play two useful moves for Black.",
                "hints": ["Start by developing the bishop."],
                "tree": [
                    {
                        "uci": "f8g7",
                        "role": "learner",
                        "outcome": "continue",
                        "feedback": "Good. The bishop is active.",
                        "children": [{
                            "uci": "d2d4",
                            "role": "opponent",
                            "outcome": "reply",
                            "feedback": "White builds the centre. Now finish the plan.",
                            "children": [
                                {
                                    "uci": "e8g8",
                                    "role": "learner",
                                    "outcome": "preferred",
                                    "feedback": "Well done. Black developed and castled."
                                },
                                {
                                    "uci": "d7d5",
                                    "role": "learner",
                                    "outcome": "acceptable",
                                    "feedback": "This central break is useful too."
                                },
                                {
                                    "uci": "b8c6",
                                    "role": "learner",
                                    "outcome": "wrong",
                                    "feedback": "That develops, but finish king safety first."
                                }
                            ]
                        }, {
                            "uci": "e2e4",
                            "role": "opponent",
                            "outcome": "reply",
                            "feedback": "White takes more central space.",
                            "children": [{
                                "uci": "e8g8",
                                "role": "learner",
                                "outcome": "preferred",
                                "feedback": "Black can still castle safely."
                            }]
                        }]
                    },
                    {
                        "uci": "f8h6",
                        "role": "learner",
                        "outcome": "wrong",
                        "feedback": "The bishop is misplaced on h6."
                    }
                ],
                "other_legal_move_text": "That line is not reviewed here."
            }
        }],
        "takeaway": "Develop, then castle."
    }


def _tree_lesson():
    entry = _entry()
    return entry, parse_lesson_data(
        _tree_lesson_data(entry), "two-move-development.json")


def test_packaged_lesson_resolves_three_exact_positions():
    entry = _entry()
    lesson = entry.lesson
    resolved = resolve_lesson(entry.game, lesson)
    assert lesson.schema_version == 1
    assert [len(item.step.node_path) for item in resolved] == [5, 33, 81]
    assert len(lesson.steps) == 3
    assert all(step.question for step in lesson.steps)


def test_packaged_starter_collection_categories_and_endgame_claims():
    from chess_game.moves import game_status

    library = load_game_library()
    assert not library.errors
    assert len(library.entries) == 18
    assert len(library.lessons) == 18
    assert len(library.lesson_entries) == 18
    assert [entry.category for entry in library.entries].count("guided_game") == 1
    assert [entry.category for entry in library.entries].count("opening") == 9
    assert [entry.category for entry in library.entries].count("endgame") == 6
    assert [entry.category for entry in library.entries].count("source_game") == 2
    assert all(resolve_lesson(entry.game, entry.lesson)
               for entry in library.lesson_entries)
    assert all(entry.game.source.name and entry.game.source.license
               and entry.game.source.attribution for entry in library.entries)
    assert all(entry.lesson.objective and entry.lesson.commentary_source.name
               and entry.lesson.commentary_source.license
               and entry.lesson.commentary_source.attribution
               for entry in library.lesson_entries)

    mate_entry = next(entry for entry in library.lesson_entries
                      if entry.lesson.lesson_id == "mate-or-stalemate")
    mate = LessonController(mate_entry.game, mate_entry.lesson)
    mate.begin_question()
    mate.attempt_uci("b5b7")
    assert game_status(mate.board) == "checkmate"
    stalemate = LessonController(mate_entry.game, mate_entry.lesson)
    stalemate.begin_question()
    stalemate.attempt_uci("b5b6")
    assert game_status(stalemate.board) == "stalemate"

    for lesson_id in ("queen-and-king-mate", "rook-and-king-mate"):
        entry = next(entry for entry in library.lesson_entries
                     if entry.lesson.lesson_id == lesson_id)
        controller = LessonController(entry.game, entry.lesson)
        controller.begin_question()
        first = controller.attempt_uci("c6b6")
        assert first.outcome == "continue" and str(first.move) == "a8b8"
        assert controller.attempt_uci("d4d8").outcome == "preferred"
        assert game_status(controller.board) == "checkmate"


def test_bruno_scotch_lesson_changes_prompt_and_hint_after_reply():
    library = load_game_library()
    course = library.course("bruno-scotch-first-ideas")
    entry = library.lesson_entry("bruno-scotch-make-room")
    assert library.player(course.player_id).portrait == "bruno.bmp"
    assert library.course_lessons(course)[0] == entry
    assert len(library.course_lessons(course)) == 3
    lesson = LessonController(entry.game, entry.lesson)
    lesson.begin_question()
    assert "Which pawn" in lesson.active_prompt
    result = lesson.attempt_uci("d2d4")
    assert result.outcome == "continue"
    assert str(result.move) == "e5d4"
    assert "Which knight" in lesson.active_prompt
    assert "knight on f3" in lesson.request_hint()
    assert lesson.begin_exploration({"scroll": 3})
    assert lesson.return_from_exploration() == {"scroll": 3}
    assert "Which knight" in lesson.active_prompt
    assert "knight on f3" in lesson.request_hint()
    result = lesson.attempt_uci("f3d4")
    assert result.outcome == "preferred"
    assert lesson.continue_lesson() is False
    assert lesson.state == COMPLETED


def test_player_courses_have_distinct_transfer_positions_and_shared_games():
    library = load_game_library()
    assert not library.errors
    assert tuple(course.player_id for course in library.courses) == (
        "bruno-bear", "olive-owl")
    assert all(len(library.course_lessons(course)) == 3
               for course in library.courses)
    for course in library.courses:
        entries = library.course_lessons(course)
        assert entries[0].game is entries[1].game
        assert entries[2].game is not entries[0].game
        assert entries[2].lesson.steps[-1].practice_mode == "independent"
        assert all(entry.lesson.related_source_game_id == course.source_game_id
                   for entry in entries)
        assert course.association_source.url.startswith("https://")
        assert course.source_game.url == ""
    assert len(library.games_by_id) == len(library.entries)
    assert len(library.lessons_by_id) == len(library.lesson_entries)


def test_player_courses_acknowledge_good_moves_that_miss_the_question():
    library = load_game_library()
    for lesson_id, move in (
            ("bruno-scotch-try-alone", "f1c4"),
            ("olive-catalan-king-safety", "b1c3")):
        entry = library.lesson_entry(lesson_id)
        lesson = LessonController(entry.game, entry.lesson)
        lesson.begin_question()
        result = lesson.attempt_uci(move)
        assert result.outcome == "wrong"
        assert not lesson.step_solved
        assert "develop" in result.feedback


def test_revised_player_feedback_matches_the_board():
    library = load_game_library()
    scotch = library.lesson_entry("bruno-scotch-active-knight")
    lesson = LessonController(scotch.game, scotch.lesson)
    lesson.begin_question()
    assert lesson.attempt_uci("d1d4").outcome == "wrong"
    board = lesson.board
    lesson.adapter.apply_uci(board, "c6d4")
    assert board.piece_at((4, 3)) == "bn"
    assert not any(piece == "wq" for row in board.grid for piece in row)

    catalan = library.lesson_entry("olive-catalan-try-alone")
    lesson = LessonController(catalan.game, catalan.lesson)
    lesson.begin_question()
    assert lesson.attempt_uci("f1g2").outcome == "preferred"
    board = lesson.board
    assert board.piece_at((6, 6)) == "wb"  # g2
    assert board.piece_at((5, 5)) == "wn"  # f3 blocks the bishop


def test_catalog_keeps_multiple_lessons_for_one_game(monkeypatch):
    import json
    from chess_game.study import content

    original = content._read_text

    def extra_resource(package, name):
        if name == "manifest.json":
            data = json.loads(original(package, name))
            data["lessons"].append({
                "lesson_id": "shared-scotch-copy",
                "game_id": "bruno-scotch-practice",
                "file": "shared-scotch-copy.json"})
            return json.dumps(data)
        if name == "shared-scotch-copy.json":
            data = json.loads(original(package,
                                       "bruno-scotch-make-room.json"))
            data["lesson_id"] = "shared-scotch-copy"
            return json.dumps(data)
        return original(package, name)

    monkeypatch.setattr(content, "_read_text", extra_resource)
    library = load_game_library()
    assert not library.errors
    assert len(library.entries) == 18
    assert len(library.lesson_entries) == 19
    first = library.lesson_entry("bruno-scotch-make-room")
    second = library.lesson_entry("shared-scotch-copy")
    assert first.game is second.game
    assert first.lesson.lesson_id != second.lesson.lesson_id


def test_packaged_opening_and_promotion_multi_move_exercises():
    from chess_game.moves import game_status

    library = load_game_library()
    opening_entry = next(entry for entry in library.lesson_entries
                         if entry.lesson.lesson_id == "opening-essentials")
    opening = LessonController(opening_entry.game, opening_entry.lesson)
    opening.begin_question()
    first = opening.attempt_uci("e2e4")
    assert first.outcome == "continue" and str(first.move) == "e7e5"
    assert opening.attempt_uci("g1f3").outcome == "preferred"
    assert opening.continue_lesson()
    assert opening.step_index == 1

    promotion_entry = next(entry for entry in library.lesson_entries
                           if entry.lesson.lesson_id == "promote-the-pawn")
    promotion = LessonController(promotion_entry.game, promotion_entry.lesson)
    promotion.begin_question()
    pushed = promotion.attempt_uci("e6e7")
    assert pushed.outcome == "continue" and str(pushed.move) == "h2g3"
    assert promotion.attempt_uci("e7e8q").outcome == "preferred"

    underpromotion = LessonController(
        promotion_entry.game, promotion_entry.lesson)
    underpromotion.begin_question()
    underpromotion.attempt_uci("e6e7")
    assert underpromotion.attempt_uci("e7e8b").outcome == "wrong"
    assert game_status(underpromotion.board) == "draw-material"


def test_square_rule_line_really_catches_the_pawn():
    library = load_game_library()
    entry = next(entry for entry in library.lesson_entries
                 if entry.lesson.lesson_id == "square-of-the-pawn")
    lesson = LessonController(entry.game, entry.lesson)
    lesson.begin_question()
    first = lesson.attempt_uci("e5d6")
    assert first.outcome == "continue" and str(first.move) == "a4a5"
    assert lesson.attempt_uci("d6c6").outcome == "preferred"

    # Continue the claimed line outside the finite exercise tree.
    board = lesson.board
    for uci in ("a5a6", "c6b6", "a6a7", "b6a7"):
        lesson.adapter.apply_uci(board, uci)
    assert board.piece_at((1, 0)) == "bk"


def test_every_packaged_lesson_has_a_complete_assisted_path():
    library = load_game_library()
    for entry in library.lesson_entries:
        lesson = LessonController(entry.game, entry.lesson)
        while lesson.state != COMPLETED:
            if lesson.state == READING:
                lesson.begin_question()
            elif lesson.state in (QUESTION, FEEDBACK):
                if not lesson.step_solved:
                    lesson.reveal()
                lesson.continue_lesson()
            else:
                raise AssertionError(
                    "unexpected state {} in {}".format(
                        lesson.state, entry.lesson.lesson_id))
        assert lesson.reveals == len(entry.lesson.steps)


def test_every_packaged_lesson_has_a_complete_unassisted_path():
    library = load_game_library()
    for entry in library.lesson_entries:
        lesson = LessonController(entry.game, entry.lesson)
        while lesson.state != COMPLETED:
            if lesson.state == READING:
                lesson.begin_question()
            elif lesson.state == QUESTION:
                question = lesson.current_step.question
                choices = (lesson._tree_choices
                           if question.evaluator == "reviewed_tree"
                           else question.answers)
                answer = next((choice for choice in choices
                               if choice.outcome == "preferred"), None)
                if answer is None:
                    answer = next((choice for choice in choices
                                   if choice.outcome == "acceptable"), None)
                if answer is None:
                    answer = next(choice for choice in choices
                                  if choice.outcome == "continue")
                lesson.attempt_uci(answer.uci)
            elif lesson.state == FEEDBACK:
                assert lesson.step_solved
                lesson.continue_lesson()
            else:
                raise AssertionError(
                    "unexpected state {} in {}".format(
                        lesson.state, entry.lesson.lesson_id))
        assert lesson.successes == len(entry.lesson.steps)
        assert lesson.reveals == 0


def test_validation_error_names_game_lesson_and_step():
    entry = _entry()
    bad_step = replace(entry.lesson.steps[0], expected_fen="8/8/8/8/8/8/8/8 w - - 0 1")
    bad_lesson = replace(entry.lesson, steps=(bad_step,) + entry.lesson.steps[1:])
    try:
        resolve_lesson(entry.game, bad_lesson)
    except LessonValidationError as error:
        message = str(error)
        assert entry.game.game_id in message
        assert entry.lesson.lesson_id in message
        assert bad_step.step_id in message
        assert "expected FEN" in message
    else:
        raise AssertionError("a mismatched lesson position must fail")


def test_schema_two_reviewed_tree_is_parsed_and_legally_resolved():
    entry, lesson = _tree_lesson()
    assert lesson.schema_version == 2
    assert lesson.steps[0].question.evaluator == "reviewed_tree"
    assert resolve_lesson(entry.game, lesson)

    invalid = _tree_lesson_data(entry)
    invalid["steps"][0]["question"]["tree"][0]["children"][0]["uci"] = "d2d5"
    broken = parse_lesson_data(invalid, "invalid-tree.json")
    try:
        resolve_lesson(entry.game, broken)
    except LessonValidationError as error:
        assert "invalid reviewed-tree move" in str(error)
        assert "d2d5" in str(error)
    else:
        raise AssertionError("an illegal reviewed-tree branch must fail")

    old_schema = deepcopy(_tree_lesson_data(entry))
    old_schema["schema_version"] = 1
    old_lesson = parse_lesson_data(old_schema, "old-schema.json")
    try:
        resolve_lesson(entry.game, old_lesson)
    except LessonValidationError as error:
        assert "schema version 2" in str(error)
    else:
        raise AssertionError("reviewed_tree must require schema version 2")

    malformed = _tree_lesson_data(entry)
    root = malformed["steps"][0]["question"]["tree"][0]
    root["children"].append({
        "uci": "d7d5",
        "role": "learner",
        "outcome": "preferred",
        "feedback": "This has the wrong role at this depth."
    })
    try:
        parse_lesson_data(malformed, "malformed-tree.json")
    except ContentLoadError as error:
        assert "tree[0]" in str(error)
        assert "opponent replies" in str(error)
    else:
        raise AssertionError("a continuing move must contain opponent replies")


def test_multi_move_tree_applies_reply_and_completes_only_at_terminal_move():
    entry, lesson_data = _tree_lesson()
    lesson = LessonController(entry.game, lesson_data)
    lesson.begin_question()

    first = lesson.attempt_uci("f8g7")
    assert first.outcome == "continue"
    assert str(first.move) == "d2d4"
    assert "White just played d4. Your turn again." in first.feedback
    assert lesson.state == QUESTION
    assert not lesson.step_solved and lesson.attempts == 1
    after_reply = lesson.adapter.fen(lesson.board)

    uncovered = lesson.attempt_uci("c7c5", view_state={"scroll": 24})
    assert uncovered.outcome == "not_covered"
    assert "okay to try" in uncovered.feedback
    assert "Return to lesson to try again" in uncovered.feedback
    assert lesson.state == EXPLORING
    restored = lesson.return_from_exploration()
    assert restored == {"scroll": 24}
    assert lesson.adapter.fen(lesson.board) == after_reply

    final = lesson.attempt_uci("e8g8")
    assert final.outcome == "preferred"
    assert lesson.state == FEEDBACK and lesson.step_solved
    assert lesson.successes == 1 and lesson.attempts == 3


def test_multi_move_retry_and_reveal_reset_to_a_checked_line():
    entry, lesson_data = _tree_lesson()
    lesson = LessonController(entry.game, lesson_data)
    lesson.begin_question()
    wrong = lesson.attempt_uci("f8h6")
    assert wrong.outcome == "wrong"
    lesson.retry()
    assert lesson.state == QUESTION
    revealed = lesson.reveal()
    assert revealed.outcome == "revealed"
    assert str(revealed.move) == "e8g8"
    assert lesson.assisted and lesson.step_solved

    continued = LessonController(entry.game, lesson_data)
    continued.begin_question()
    continued.attempt_uci("f8g7")
    revealed_remainder = continued.reveal()
    assert str(revealed_remainder.move) == "e8g8"
    assert continued.state == FEEDBACK and continued.assisted


def test_question_outcomes_retry_hint_and_reveal():
    entry = _entry()
    lesson = LessonController(entry.game, entry.lesson)
    assert lesson.state == READING
    assert not lesson.visible_arrows
    lesson.begin_question()
    assert lesson.state == QUESTION and lesson.future_source_hidden

    hint = lesson.request_hint()
    assert "bishop" in hint.lower()
    wrong = lesson.attempt_uci("f8h6")
    assert wrong.outcome == "wrong" and lesson.state == FEEDBACK
    assert not lesson.step_solved and not lesson.visible_arrows

    lesson.retry()
    accepted = lesson.attempt_uci("d7d5")
    assert accepted.outcome == "acceptable"
    assert lesson.step_solved and lesson.visible_arrows
    assert lesson.continue_lesson()

    lesson.begin_question()
    revealed = lesson.reveal()
    assert revealed.outcome == "revealed"
    assert lesson.assisted and lesson.reveals == 1


def test_uncovered_exploration_returns_to_exact_question_state():
    entry = _entry()
    lesson = LessonController(entry.game, entry.lesson)
    lesson.begin_question()
    expected_fen = lesson.adapter.fen(lesson.board)
    result = lesson.attempt_uci("b8c6")
    assert result.outcome == "not_covered"
    assert lesson.state == EXPLORING
    assert lesson.adapter.fen(lesson.board) != expected_fen
    lesson.explore_uci("d2d4")
    restored_view = lesson.return_from_exploration()
    assert restored_view is None
    assert lesson.state == QUESTION
    assert lesson.adapter.fen(lesson.board) == expected_fen
    assert lesson.replay.ply == 5


def test_both_mates_are_successful_and_completion_is_distinct():
    entry = _entry()
    for move, outcome in (("a2c2", "preferred"), ("b4a3", "acceptable")):
        lesson = LessonController(entry.game, entry.lesson, resume_step=2)
        lesson.begin_question()
        result = lesson.attempt_uci(move)
        assert result.outcome == outcome
        assert lesson.continue_lesson() is False
        assert lesson.state == COMPLETED


def test_board_annotations_draw_and_respect_flip():
    entry = _entry()
    lesson = LessonController(entry.game, entry.lesson)
    lesson.begin_question()
    lesson.attempt_uci("f8g7")
    pygame.init()
    surface = pygame.Surface((320, 320))
    piece_font = pygame.font.SysFont("dejavusans", 34)
    label_font = pygame.font.SysFont("monospace", 16, bold=True)
    view = BoardView(surface, 0, 0, 40, piece_font, label_font,
                     use_glyphs=False)
    view.draw_base()
    before = surface.copy()
    view.draw_position(
        lesson.board, white_color=(245, 245, 245), black_color=(32, 32, 32),
        lesson_highlights=lesson.visible_highlights,
        lesson_arrows=lesson.visible_arrows)
    assert pygame.image.tobytes(surface, "RGB") != pygame.image.tobytes(before, "RGB")
    view.flipped = True
    assert view.pixel_to_square(view.square_to_pixel((1, 6))) == (1, 6)
    pygame.quit()


def test_lesson_ui_plays_a_question_and_keeps_panel_on_narrow_windows():
    import tempfile
    from pathlib import Path
    from chess_game.ui import ChessUI

    with tempfile.TemporaryDirectory() as directory:
        ui = ChessUI(":memory:")
        ui.progress_store.close()
        ui.progress_store = ProgressStore(Path(directory) / "progress.sqlite3")
        entry = next(entry for entry in ui.game_library.entries
                     if entry.game.game_id == "coordination-study")
        ui.start_lesson(entry)
        assert ui.scene == "lesson"
        assert ui.lesson.state == QUESTION
        assert not ui.thinking

        bishop = ui._sq_to_px((0, 5))
        target = ui._sq_to_px((1, 6))
        ui._on_mouse_down((bishop[0] + ui.SQ // 2,
                           bishop[1] + ui.SQ // 2))
        ui._on_mouse_up((bishop[0] + ui.SQ // 2,
                         bishop[1] + ui.SQ // 2))
        ui._on_mouse_down((target[0] + ui.SQ // 2,
                           target[1] + ui.SQ // 2))
        assert ui.lesson.state == FEEDBACK
        assert ui.lesson.last_attempt.outcome == "preferred"
        ui._build_lesson_buttons()
        ui._draw()
        assert ui.lesson_scroll == ui.lesson_max_scroll

        ui._lesson_continue()
        ui._lesson_start_question()
        source_fen = ui.lesson.adapter.fen(ui.board)
        ui.lesson_scroll = 48
        uncovered = next(move for move in ui.lesson.adapter.legal_moves(ui.board)
                         if str(move) == "b6b5")
        assert ui._apply_lesson_move(uncovered)
        assert ui.lesson.state == EXPLORING
        ui._lesson_return()
        assert ui.lesson.state == QUESTION
        assert ui.lesson_scroll == 48
        assert ui.lesson.adapter.fen(ui.board) == source_fen
        ui._lesson_hint()
        ui._lesson_reveal()
        assert ui.lesson.assisted
        ui._lesson_continue()

        ui._lesson_start_question()
        alternate_mate = next(
            move for move in ui.lesson.adapter.legal_moves(ui.board)
            if str(move) == "b4a3")
        assert ui._apply_lesson_move(alternate_mate)
        assert ui.lesson.last_attempt.outcome == "acceptable"
        ui._lesson_continue()
        assert ui.lesson.state == COMPLETED
        assert ui.progress_store.load(entry.lesson.lesson_id).completed

        ui._on_resize(640, 700)
        ui._build_lesson_buttons()
        assert ui.show_panel
        assert ui.panel_x >= 0 and ui.panel_y > ui.board_y
        assert ui.panel_x + ui.panel_w <= ui.win_w
        assert ui.panel_y + ui.panel_h <= ui.win_h
        ui._draw()
        ui._lesson_restart()
        assert ui.lesson.state == QUESTION and ui.lesson.step_index == 0
        ui.progress_store.close()
        pygame.quit()


def test_lesson_ui_handles_authored_opponent_reply_in_multi_move_tree():
    from chess_game.ui import ChessUI

    entry, lesson_data = _tree_lesson()
    ui = ChessUI(":memory:")
    ui.start_lesson(replace(entry, lesson=lesson_data))
    ui._lesson_start_question()
    bishop = next(move for move in ui.lesson.adapter.legal_moves(ui.board)
                  if str(move) == "f8g7")
    assert ui._apply_lesson_move(bishop)
    assert ui.lesson.state == QUESTION
    assert str(ui.last_move) == "d2d4"
    castle = next(move for move in ui.lesson.adapter.legal_moves(ui.board)
                  if str(move) == "e8g8")
    assert ui._apply_lesson_move(castle)
    assert ui.lesson.state == FEEDBACK
    ui._build_lesson_buttons()
    ui._draw()
    ui.progress_store.close()
    pygame.quit()


def main():
    for name, function in sorted(globals().items()):
        if name.startswith("test_") and callable(function):
            function()
            print("ok ", name)
    print("\nall guided lesson tests passed")


if __name__ == "__main__":
    main()
