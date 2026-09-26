"""Immutable replay navigation and packaged-library checks."""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from chess_game.study import (
    ReplayController,
    ReplayNavigationError,
    load_game_library,
    parse_pgn_games,
)

from .test_pgn_import import ANNOTATED_PGN


def test_mainline_and_variation_navigation():
    game = parse_pgn_games(ANNOTATED_PGN)[0]
    source_before = repr(game.root)
    replay = ReplayController(game)

    assert replay.mainline_length() == 4
    assert replay.mainline_sans() == ("e4", "e5", "Nf3", "Nc6")
    assert replay.ply == 0
    assert replay.next()
    assert replay.uci_path() == ("e2e4",)
    assert replay.variation_count == 2

    assert replay.next(1)
    assert replay.uci_path() == ("e2e4", "c7c5")
    assert replay.current_comment == "The Sicilian Defence."
    assert replay.next()
    assert replay.sans == ("e4", "c5", "Nf3")
    assert replay.previous()
    assert replay.uci_path() == ("e2e4", "c7c5")

    replay.go_first()
    replay.go_last()
    assert replay.uci_path() == ("e2e4", "e7e5", "g1f3", "b8c6")
    assert repr(game.root) == source_before


def test_arbitrary_jump_restores_exact_position():
    game = parse_pgn_games(ANNOTATED_PGN)[0]
    replay = ReplayController(game)
    replay.jump_mainline(3)
    expected = replay.board
    replay.go_first()
    replay.jump((0, 0, 0))
    assert replay.adapter.fen(replay.board) == replay.adapter.fen(expected)


def test_invalid_jump_does_not_change_current_position():
    game = parse_pgn_games(ANNOTATED_PGN)[0]
    replay = ReplayController(game)
    replay.next()
    position = replay.adapter.fen(replay.board)
    try:
        replay.jump((99,))
    except ReplayNavigationError:
        pass
    else:
        raise AssertionError("invalid replay path must fail")
    assert replay.path == (0,)
    assert replay.adapter.fen(replay.board) == position
    try:
        replay.jump((-1,))
    except ReplayNavigationError:
        pass
    else:
        raise AssertionError("negative replay indexes must fail")
    assert replay.path == (0,)


def test_custom_black_to_move_start():
    game = parse_pgn_games(ANNOTATED_PGN)[1]
    replay = ReplayController(game)
    assert replay.mainline_sans() == ("Kf4", "Kf2")
    replay.next()
    assert replay.uci_path() == ("e5f4",)


def test_packaged_library_game_is_complete_and_sourced():
    library = load_game_library()
    assert not library.errors
    assert len(library.entries) == 18
    entry = next(entry for entry in library.entries
                 if entry.game.game_id == "coordination-study")
    assert entry.game.game_id == "coordination-study"
    assert entry.game.source.url == ""
    replay = ReplayController(entry.game)
    assert replay.mainline_length() == 82
    assert replay.mainline_sans()[-1] == "Rc2#"
    replay.go_last()
    assert replay.game.result == "0-1"


def test_player_course_source_games_are_bundled_and_replayable():
    library = load_game_library()
    assert not library.errors
    for course, expected_plies in zip(library.courses, (80, 116)):
        entry = next(item for item in library.entries
                     if item.game.game_id == course.source_game_id)
        assert entry.category == "source_game"
        assert entry.game.source.url == course.source_game.url
        replay = ReplayController(entry.game)
        assert replay.mainline_length() == expected_plies
        replay.go_last()
        assert replay.game.result == "1/2-1/2"


def test_replay_ui_never_starts_computer_opponent():
    import pygame
    from chess_game.ui import ChessUI

    ui = ChessUI(":memory:")
    entry = next(entry for entry in ui.game_library.entries
                 if entry.game.game_id == "coordination-study")
    ui.start_replay(entry)
    assert ui.scene == "replay"
    assert not ui.thinking
    assert ui.replay.ply == 0

    ui._build_replay_buttons()
    ui._draw()
    assert ui._replay_move_hits
    assert ui.replay_max_scroll > 0

    first_visible_ply = ui._replay_move_hits[0][1]
    ui._scroll_replay(5)
    assert ui.replay_scroll_manual
    assert ui.replay_scroll == 5
    assert not ui.replay_autoplay
    ui._draw()
    assert ui._replay_move_hits[0][1] == first_visible_ply + 5

    old_scroll = ui.replay_scroll
    ui._on_key(pygame.K_PAGEDOWN)
    assert ui.replay_scroll > old_scroll
    ui._draw()

    move_rect, expected_ply = ui._replay_move_hits[3]
    ui._on_mouse_down(move_rect.center)
    assert ui.replay.ply == expected_ply
    assert not ui.replay_scroll_manual
    assert not ui.thinking

    ui._replay_first()
    ui.replay_autoplay = True
    ui.replay_next_at = 0
    assert ui._poll_replay_autoplay()
    assert ui.replay.ply == 1
    assert not ui.thinking

    ui._replay_next()
    assert ui.replay.ply == 2
    assert not ui.thinking

    ui._replay_last()
    assert ui.replay.ply == 82
    assert ui.status == "checkmate"
    ui._draw()
    assert any(ply == 82 for _rect, ply in ui._replay_move_hits)
    assert ui.replay_scroll == ui.replay_max_scroll
    ui.progress_store.close()
    pygame.quit()


def test_completed_player_lessons_watch_source_and_return_to_same_lesson():
    import pygame
    from chess_game.ui import ChessUI
    from chess_game.study import COMPLETED

    ui = ChessUI(":memory:")
    for course in ui.game_library.courses:
        for entry in ui.game_library.course_lessons(course):
            ui.start_lesson(entry, course_id=course.course_id)
            ui._lesson_reveal()
            ui._lesson_continue()
            assert ui.lesson.state == COMPLETED
            controller = ui.lesson
            coach = ui.coach_profile
            successes = controller.successes
            ui._watch_lesson_record()
            assert ui.replay_entry.game.game_id == course.source_game_id
            ui._on_key(pygame.K_ESCAPE)
            assert ui.scene == "lesson"
            assert ui.lesson is controller
            assert ui.lesson.state == COMPLETED
            assert ui.lesson.successes == successes
            assert ui.coach_profile is coach
            assert ui._next_path_entry() == (
                ui.game_library.lesson_entry(course.lesson_ids[
                    course.lesson_ids.index(entry.lesson.lesson_id) + 1])
                if entry.lesson.lesson_id != course.lesson_ids[-1] else None)
    ui.progress_store.close()
    pygame.quit()


def test_replay_returns_to_source_page_and_watch_list():
    import pygame
    from chess_game.ui import ChessUI

    ui = ChessUI(":memory:")
    course = ui.game_library.courses[0]
    ui._open_course(course.course_id)
    ui._open_course_about()
    ui._watch_course_source()
    ui._leave_replay()
    assert (ui.scene, ui.menu_view, ui.active_course_id) == (
        "menu", "course_about", course.course_id)
    assert ui._menu_buttons[ui._button_focus].value == "source_game"

    ui._open_library("replay")
    entry = next(item for item in ui.game_library.entries
                 if item.game.game_id == course.source_game_id)
    ui.start_replay(entry)
    ui._on_key(pygame.K_ESCAPE)
    assert (ui.scene, ui.menu_view, ui.library_filter) == (
        "menu", "library", "replay")
    assert ui._menu_buttons[ui._button_focus].value == course.source_game_id
    ui.progress_store.close()
    pygame.quit()


def test_historical_replay_titles_fit_and_do_not_overlap_notes():
    import pygame
    from chess_game.ui import ChessUI
    from chess_game.views.study_view import _wrap_text

    ui = ChessUI(":memory:")
    entries = [entry for entry in ui.game_library.entries
               if entry.category == "source_game"]
    for entry in entries:
        ui.start_replay(entry)
        for width, height in ((360, 700), (420, 720), (600, 600),
                              (819, 760), (821, 760), (980, 760)):
            ui._on_resize(width, height)
            for scale in (1.0, 1.2, 1.4):
                ui._set_text_scale(scale)
                ui._build_replay_buttons()
                ui._draw()
                view = ui.study_view
                panel = pygame.Rect(ui.panel_x, ui.panel_y,
                                    ui.panel_w, ui.panel_h)
                assert panel.contains(view.replay_title_rect)
                assert panel.contains(view.replay_note_rect)
                assert panel.contains(view.replay_moves_rect)
                assert view.replay_title_rect.bottom <= view.replay_note_rect.top
                assert view.replay_note_rect.bottom <= view.replay_moves_rect.top
                assert view.replay_moves_rect.bottom <= min(
                    button.rect.top for button in ui._game_buttons)
                for line in _wrap_text(ui.status_font, entry.title,
                                       view.replay_title_rect.w):
                    assert ui.status_font.size(line)[0] <= view.replay_title_rect.w
    ui.progress_store.close()
    pygame.quit()


def main():
    for name, function in sorted(globals().items()):
        if name.startswith("test_") and callable(function):
            function()
            print("ok ", name)
    print("\nall replay tests passed")


if __name__ == "__main__":
    main()
