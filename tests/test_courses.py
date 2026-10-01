"""Course format compatibility and the first character teaching path."""

from dataclasses import replace
import json

from chess_game.study import COMPLETED, LessonController, load_game_library
from chess_game.study import content


def _courses_with(monkeypatch, data, lessons=None):
    library = load_game_library()
    original = content._read_text

    def read(package, name):
        if name == "courses.json":
            return json.dumps(data)
        return original(package, name)

    monkeypatch.setattr(content, "_read_text", read)
    errors = []
    players, courses = content._load_player_courses(
        "chess_game.content.starter",
        lessons if lessons is not None else library.lesson_entries,
        library.entries, errors)
    return players, courses, errors


def test_legacy_course_records_still_load(monkeypatch):
    data = json.loads(content._read_text(
        "chess_game.content.starter", "courses.json"))
    data["schema_version"] = 1
    data["courses"] = data["courses"][:2]
    for item in data["courses"]:
        for field in ("category", "content_kind", "objective",
                      "assumed_knowledge", "completion_policy"):
            item.pop(field)
    players, courses, errors = _courses_with(monkeypatch, data)
    assert not errors
    assert {course.course_id for course in courses} == {
        "bruno-scotch-first-ideas", "olive-catalan-first-ideas"}
    assert all(course.category == "opening" and
               course.completion_policy == "independent_final"
               for course in courses)
    assert {course.player_id for course in courses}.issubset(
        {player.player_id for player in players})


def test_general_courses_validate_lengths_references_and_drafts(monkeypatch):
    library = load_game_library()
    data = json.loads(content._read_text(
        "chess_game.content.starter", "courses.json"))
    template = next(item for item in data["courses"]
                    if item["course_id"] == "chicky-first-knight-steps")
    assert len(library.course_lessons(library.course(
        "chicky-first-knight-steps"))) == 7
    assert library.courses_for_category("movement")[0].player_id == "chicky"

    for count in (1, 3, 7):
        entries = list(library.lesson_entries)
        ids = ["chicky-knight-steps"]
        base = library.lesson_entry("chicky-knight-steps")
        for index in range(1, count):
            ident = "extra-knight-{}".format(index)
            ids.append(ident)
            entries.append(replace(base, lesson=replace(
                base.lesson, lesson_id=ident)))
        item = dict(template, course_id="length-{}".format(count),
                    lesson_ids=ids)
        variant = dict(data, courses=[item])
        _, courses, errors = _courses_with(monkeypatch, variant, tuple(entries))
        assert not errors
        assert len(courses[0].lesson_ids) == count

    for bad_ids in (["chicky-knight-steps", "chicky-knight-steps"],
                    ["missing-lesson"]):
        variant = dict(data, courses=[dict(template, lesson_ids=bad_ids)])
        _, courses, errors = _courses_with(monkeypatch, variant)
        assert not courses and errors

    draft = dict(template, course_id="draft-knight", published=False)
    variant = dict(data, courses=[draft])
    _, courses, errors = _courses_with(monkeypatch, variant)
    assert not errors and not courses[0].published


def test_monty_course_rejects_missing_source_and_unknown_lock(monkeypatch):
    data = json.loads(content._read_text(
        "chess_game.content.starter", "courses.json"))
    monty = next(item for item in data["courses"]
                 if item["course_id"] == "monty-amsterdam-analysis")
    for change in (
            {"source_game_id": "missing-score"},
            {"source_game": dict(monty["source_game"], url="")},
            {"entitlement_id": "unknown-lock"}):
        item = dict(monty, **change)
        _, courses, errors = _courses_with(
            monkeypatch, dict(data, courses=[item]))
        assert not courses and errors


def test_chicky_knight_lesson_accepts_related_independent_jump():
    library = load_game_library()
    entry = library.lesson_entry("chicky-knight-steps")
    lesson = LessonController(entry.game, entry.lesson)
    lesson.begin_question()
    assert lesson.attempt_uci("g1f3").outcome == "preferred"
    assert lesson.continue_lesson()
    assert lesson.current_step.practice_mode == "independent"
    assert not lesson.visible_highlights
    lesson.begin_question()
    assert lesson.attempt_uci("f3h4").outcome == "acceptable"
    assert not lesson.continue_lesson()
    assert lesson.state == COMPLETED


def test_beginner_moves_and_captures_keep_wrong_attempts_on_the_board():
    from chess_game.study import ChessAdapter, ProgressStore

    library = load_game_library()
    cases = (
        ("chicky-pawn-steps", "e2e4", "e2e3", "e3d4", "d4"),
        ("chicky-rook-lines", "a2a3", "a2a4", "a4d4", "d4"),
        ("chicky-bishop-diagonals", "c1e3", "c1f4", "f4h6", "h6"),
        ("chicky-queen-routes", "d1d3", "d1d4", "d4g7", "g7"),
    )
    with ProgressStore(":memory:") as store:
        for ident, wrong, first, capture, square in cases:
            entry = library.lesson_entry(ident)
            lesson = LessonController(entry.game, entry.lesson)
            lesson.begin_question()
            fen = ChessAdapter.fen(lesson.board)
            assert lesson.attempt_uci(wrong).outcome == "wrong"
            assert ChessAdapter.fen(lesson.board) == fen
            lesson.retry()
            assert lesson.attempt_uci(first).outcome == "preferred"
            lesson.continue_lesson()
            lesson.begin_question()
            assert lesson.current_step.practice_mode == "independent"
            assert not lesson.visible_highlights
            row, col = 8 - int(square[1]), ord(square[0]) - ord("a")
            assert lesson.board.piece_at((row, col)) == "bp"
            assert lesson.attempt_uci(capture).outcome in ("preferred", "acceptable")
            assert lesson.board.piece_at((row, col)).startswith("w")
            lesson.continue_lesson()
            assert lesson.state == COMPLETED
            store.save(lesson)
            assert store.load(ident).completed
            assert store.load_step_progress(ident, 1)["try-a-capture"].outcome == "independent"


def test_chicky_king_lesson_accepts_every_safe_escape():
    from chess_game.study import ChessAdapter, ProgressStore

    entry = load_game_library().lesson_entry("chicky-king-safety")
    with ProgressStore(":memory:") as store:
        for escape in ("d1c2", "d1d2", "d1e2"):
            lesson = LessonController(entry.game, entry.lesson)
            lesson.begin_question()
            fen = ChessAdapter.fen(lesson.board)
            assert lesson.attempt_uci("e1f1").outcome == "wrong"
            assert ChessAdapter.fen(lesson.board) == fen
            lesson.retry()
            assert lesson.attempt_uci("e1d1").outcome == "preferred"
            lesson.continue_lesson()
            assert lesson.current_step.practice_mode == "independent"
            assert not lesson.visible_highlights
            lesson.begin_question()
            assert {str(move) for move in ChessAdapter.legal_moves(lesson.board)} == {
                "d1c2", "d1d2", "d1e2"}
            assert lesson.attempt_uci(escape).outcome in ("preferred", "acceptable")
            lesson.continue_lesson()
            assert lesson.state == COMPLETED
            store.save(lesson)
            assert store.load_step_progress("chicky-king-safety", 1)[
                "escape-check"].outcome == "independent"


def test_chicky_simple_mate_requires_a_finish_not_just_check():
    from chess_game.moves import game_status
    from chess_game.study import ChessAdapter, ProgressStore

    entry = load_game_library().lesson_entry("chicky-simple-mate")
    lesson = LessonController(entry.game, entry.lesson)
    lesson.begin_question()
    initial_fen = ChessAdapter.fen(lesson.board)
    assert lesson.attempt_uci("b4a5").outcome == "wrong"
    assert ChessAdapter.fen(lesson.board) == initial_fen
    lesson.retry()
    assert lesson.attempt_uci("b4b5").outcome == "preferred"
    lesson.continue_lesson()
    assert lesson.current_step.practice_mode == "independent"
    assert not lesson.visible_highlights
    lesson.begin_question()
    final_fen = ChessAdapter.fen(lesson.board)
    assert lesson.attempt_uci("b5a6").outcome == "wrong"
    assert ChessAdapter.fen(lesson.board) == final_fen
    lesson.retry()
    assert lesson.attempt_uci("b5b7").outcome == "preferred"
    assert game_status(lesson.board) == "checkmate"
    lesson.continue_lesson()
    assert lesson.state == COMPLETED
    with ProgressStore(":memory:") as store:
        store.save(lesson)
        assert store.load_step_progress("chicky-simple-mate", 1)[
            "find-mate"].outcome == "independent"


def test_pippa_development_has_a_related_independent_move():
    from chess_game.study import ChessAdapter, ProgressStore

    library = load_game_library()
    course = library.course("pippa-develop-first-ideas")
    assert course.player_id == "pippa-pomeranian"
    assert course.category == "opening" and course.content_kind == "original"
    assert course.lesson_ids == ("pippa-develop-pieces",)
    entry = library.lesson_entry(course.lesson_ids[0])
    lesson = LessonController(entry.game, entry.lesson)
    lesson.begin_question()
    assert lesson.attempt_uci("f1c4").outcome == "preferred"
    lesson.continue_lesson()
    assert lesson.current_step.practice_mode == "independent"
    lesson.begin_question()
    fen = ChessAdapter.fen(lesson.board)
    assert lesson.attempt_uci("b1a3").outcome == "wrong"
    assert ChessAdapter.fen(lesson.board) == fen
    lesson.retry()
    assert lesson.attempt_uci("b1c3").outcome == "preferred"
    lesson.continue_lesson()
    assert lesson.state == COMPLETED
    with ProgressStore(":memory:") as store:
        store.save(lesson)
        assert store.load_step_progress(entry.lesson.lesson_id, 1)[
            "independent-knight"].outcome == "independent"


def test_tina_promotion_keeps_a_wrong_piece_choice_retryable():
    from chess_game.study import ChessAdapter, ProgressStore

    library = load_game_library()
    course = library.course("tina-first-promotion")
    assert course.category == "endgame" and course.content_kind == "original"
    assert course.lesson_ids == (
        "tina-first-promotion", "tina-active-king", "mate-or-stalemate")
    entry = library.lesson_entry(course.lesson_ids[0])
    lesson = LessonController(entry.game, entry.lesson)
    lesson.begin_question()
    assert lesson.attempt_uci("a6a7").outcome == "preferred"
    lesson.continue_lesson()
    assert lesson.current_step.practice_mode == "independent"
    lesson.begin_question()
    fen = ChessAdapter.fen(lesson.board)
    assert lesson.attempt_uci("a7a8r").outcome == "wrong"
    assert ChessAdapter.fen(lesson.board) == fen
    lesson.retry()
    assert lesson.attempt_uci("a7a8q").outcome == "preferred"
    assert lesson.board.piece_at((0, 0)) == "wq"
    lesson.continue_lesson()
    assert lesson.state == COMPLETED
    with ProgressStore(":memory:") as store:
        store.save(lesson)
        assert store.load_step_progress("tina-first-promotion", 1)[
            "make-a-queen"].outcome == "independent"


def test_tina_active_king_accepts_safe_independent_approaches():
    from chess_game.study import ChessAdapter, ProgressStore

    library = load_game_library()
    course = library.course("tina-first-promotion")
    assert len(library.course_lessons(course)) == 3
    entry = library.lesson_entry("tina-active-king")
    for finish in ("d3c4", "d3e4"):
        lesson = LessonController(entry.game, entry.lesson)
        lesson.begin_question()
        assert lesson.request_hint()
        assert lesson.attempt_uci("c3d3").outcome == "preferred"
        lesson.continue_lesson()
        assert lesson.current_step.practice_mode == "independent"
        lesson.begin_question()
        fen = ChessAdapter.fen(lesson.board)
        assert lesson.attempt_uci("d3e3").outcome == "wrong"
        assert ChessAdapter.fen(lesson.board) == fen
        lesson.retry()
        assert lesson.attempt_uci(finish).outcome in ("preferred", "acceptable")
        lesson.continue_lesson()
        assert lesson.state == COMPLETED
        with ProgressStore(":memory:") as store:
            store.save(lesson)
            steps = store.load_step_progress("tina-active-king", 1)
            assert steps["support-the-pawn"].outcome == "helped"
            assert steps["approach-safely"].outcome == "independent"


def test_tina_course_reuses_stalemate_lesson_as_independent_finish():
    from chess_game.study import ChessAdapter, ProgressStore

    library = load_game_library()
    course = library.course("tina-first-promotion")
    entry = library.course_lessons(course)[-1]
    assert entry.lesson.lesson_id == "mate-or-stalemate"
    assert entry.lesson.coach_player_id == course.player_id
    assert entry.lesson.steps[-1].practice_mode == "independent"
    assert not entry.lesson.steps[-1].arrows
    assert not entry.lesson.steps[-1].highlights
    lesson = LessonController(entry.game, entry.lesson)
    lesson.begin_question()
    fen = ChessAdapter.fen(lesson.board)
    assert "stalemate" in lesson.attempt_uci("b5b6").feedback.lower()
    assert ChessAdapter.fen(lesson.board) == fen
    lesson.retry()
    assert lesson.attempt_uci("b5b7").outcome == "preferred"
    lesson.continue_lesson()
    assert lesson.state == COMPLETED
    with ProgressStore(":memory:") as store:
        store.save(lesson)
        assert store.load_step_progress("mate-or-stalemate", 3)[
            "give-checkmate"].outcome == "independent"


def test_tom_answers_a_knight_threat_with_reviewed_alternatives():
    from chess_game.study import ChessAdapter, ProgressStore

    library = load_game_library()
    course = library.course("tom-answer-the-threat")
    assert course.category == "opening" and course.content_kind == "original"
    assert course.lesson_ids == ("black-against-e4",)
    entry = library.course_lessons(course)[0]
    assert entry.lesson.coach_player_id == "tom-rabbit"
    for reply in ("b8c6", "g8f6", "d7d6"):
        lesson = LessonController(entry.game, entry.lesson)
        lesson.begin_question()
        lesson.request_hint()
        assert lesson.attempt_uci("e7e5").outcome == "preferred"
        lesson.continue_lesson()
        assert lesson.current_step.practice_mode == "independent"
        lesson.begin_question()
        fen = ChessAdapter.fen(lesson.board)
        wrong = lesson.attempt_uci("f7f6")
        assert wrong.outcome == "wrong" and "king" in wrong.feedback
        assert ChessAdapter.fen(lesson.board) == fen
        lesson.retry()
        assert lesson.attempt_uci(reply).outcome in ("preferred", "acceptable")
        lesson.continue_lesson()
        assert lesson.state == COMPLETED
        with ProgressStore(":memory:") as store:
            store.save(lesson)
            steps = store.load_step_progress("black-against-e4", 3)
            assert steps["claim-the-centre"].outcome == "helped"
            assert steps["develop-with-tempo"].outcome == "independent"


def test_bruno_improves_bishop_then_uses_open_file():
    from chess_game.study import ChessAdapter, ProgressStore

    library = load_game_library()
    course = library.course("bruno-find-a-plan")
    assert course.category == "middlegame"
    assert course.lesson_ids == ("bruno-activate-pieces",)
    entry = library.course_lessons(course)[0]
    assert entry.lesson.coach_player_id == "bruno-bear"
    lesson = LessonController(entry.game, entry.lesson)
    lesson.begin_question()
    assert lesson.attempt_uci("c1e3").outcome == "preferred"
    lesson.continue_lesson()
    assert lesson.current_step.practice_mode == "independent"
    lesson.begin_question()
    fen = ChessAdapter.fen(lesson.board)
    wrong = lesson.attempt_uci("a1b1")
    assert wrong.outcome == "wrong" and "b2 pawn" in wrong.feedback
    assert ChessAdapter.fen(lesson.board) == fen
    lesson.retry()
    assert lesson.attempt_uci("a1c1").outcome == "preferred"
    lesson.continue_lesson()
    assert lesson.state == COMPLETED
    with ProgressStore(":memory:") as store:
        store.save(lesson)
        steps = store.load_step_progress("bruno-activate-pieces", 1)
        assert steps["wake-the-bishop"].outcome == "independent"
        assert steps["use-the-open-file"].outcome == "independent"


def test_olivia_knight_fork_checks_king_then_wins_queen():
    from chess_game.study import ChessAdapter, ProgressStore

    library = load_game_library()
    course = library.course("olivia-spot-a-fork")
    assert course.category == "tactics"
    entry = library.course_lessons(course)[0]
    assert entry.lesson.coach_player_id == "olive-owl"
    _, _, continuation = ChessAdapter.replay(
        ("g5f7", "h8g8", "f7d8", "a8d8"), entry.game.starting_fen)
    assert continuation == ("Nf7+", "Kg8", "Nxd8", "Rxd8")
    lesson = LessonController(entry.game, entry.lesson)
    lesson.begin_question()
    fen = ChessAdapter.fen(lesson.board)
    wrong = lesson.attempt_uci("g5h7")
    assert wrong.outcome == "wrong" and "king" in wrong.feedback
    assert ChessAdapter.fen(lesson.board) == fen
    lesson.retry()
    assert lesson.attempt_uci("g5f7").outcome == "preferred"
    lesson.continue_lesson()
    assert lesson.current_step.practice_mode == "independent"
    lesson.begin_question()
    assert lesson.attempt_uci("f7d8").outcome == "preferred"
    lesson.continue_lesson()
    assert lesson.state == COMPLETED
    with ProgressStore(":memory:") as store:
        store.save(lesson)
        steps = store.load_step_progress("olivia-knight-fork", 1)
        assert steps["find-the-fork"].outcome == "independent"
        assert steps["take-the-queen"].outcome == "independent"


def test_monty_analysis_predicts_recorded_moves_and_preserves_source():
    from chess_game.study import ProgressStore, ReplayController

    library = load_game_library()
    course = library.course("monty-amsterdam-analysis")
    assert course.entitlement_id == "monty-first-verified-win"
    assert course.content_kind == "historical_analysis"
    assert "Lasker" not in course.association_source.name
    assert "Bauer" not in course.source_game.name
    entry = library.course_lessons(course)[0]
    assert entry.game.game_id == course.source_game_id
    assert "Lasker" not in entry.game.source.name
    assert entry.game.headers["White"] == "Recorded White"
    assert entry.game.headers["Black"] == "Recorded Black"
    assert entry.game.result == "1-0"
    assert ReplayController(entry.game).mainline_length() == 75
    lesson = LessonController(entry.game, entry.lesson)
    lesson.begin_question()
    assert lesson.attempt_uci("d3h7").outcome == "preferred"
    lesson.continue_lesson()
    assert lesson.current_step.practice_mode == "independent"
    lesson.begin_question()
    assert lesson.attempt_uci("f1f2").outcome == "wrong"
    lesson.retry()
    assert lesson.attempt_uci("f1f3").outcome == "preferred"
    lesson.continue_lesson()
    assert lesson.state == COMPLETED
    with ProgressStore(":memory:") as store:
        store.save(lesson)
        steps = store.load_step_progress("monty-amsterdam-analysis", 1)
        assert steps["first-bishop-offer"].outcome == "independent"
        assert steps["bring-the-rook"].outcome == "independent"
