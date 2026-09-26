"""Shared-widget and keyboard-access checks."""

import os
import threading
import time
from dataclasses import replace
from types import SimpleNamespace

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from chess_game import sound
from chess_game.moves import legal_moves
from chess_game.ui import ChessUI, WHITE_PRESETS, _fit_text, _wrap_text
from chess_game.chess_thoughts import THOUGHTS
from chess_game.study.coaching import coach_advice
from chess_game.views.chess_thought_view import draw_chess_thought
from chess_game.views import draw_focus_ring


def test_focus_ring_is_visibly_rendered():
    pygame.init()
    surface = pygame.Surface((80, 50))
    surface.fill((0, 0, 0))
    before = pygame.image.tobytes(surface, "RGB")
    draw_focus_ring(surface, (20, 15, 40, 20), (80, 180, 255), 6)
    assert pygame.image.tobytes(surface, "RGB") != before
    pygame.quit()


def test_tab_focus_cycles_and_activates_menu_buttons():
    ui = ChessUI(":memory:")
    ui._build_menu_buttons()
    assert ui._button_focus is None

    ui._on_key(pygame.K_TAB)
    assert ui._button_focus == 0
    ui._on_key(pygame.K_TAB, pygame.KMOD_SHIFT)
    assert ui._button_focus == len(ui._menu_buttons) - 1

    ui._on_key(pygame.K_RIGHT)
    assert ui._button_focus is None

    ui._button_focus = 1
    ui._on_key(pygame.K_RETURN)
    assert ui.menu_view == "play"
    assert ui._button_focus is None
    ui.progress_store.close()
    pygame.quit()


def test_keyboard_focus_is_visible_on_menu():
    ui = ChessUI(":memory:")
    ui._build_menu_buttons()
    ui._draw()
    before = pygame.image.tobytes(ui.screen, "RGB")
    ui._on_key(pygame.K_TAB)
    ui._draw()
    assert pygame.image.tobytes(ui.screen, "RGB") != before
    ui.progress_store.close()
    pygame.quit()


def test_appearance_preferences_survive_restart(tmp_path):
    path = tmp_path / "user-data.sqlite3"
    ui = ChessUI(path)
    standard_height = ui.text_font.get_height()
    ui._set_text_scale(1.4)
    ui._set_style("Ocean")
    ui._set_white(WHITE_PRESETS[2])
    ui._cycle_difficulty(1)
    ui._cycle_replay_speed()
    ui._toggle_sound()
    assert ui.text_font.get_height() > standard_height
    ui.progress_store.close()
    pygame.quit()

    reopened = ChessUI(path)
    assert reopened.text_scale == 1.4
    assert reopened.board_style == "Ocean"
    assert reopened.white_col == WHITE_PRESETS[2]
    assert reopened.difficulty == 2
    assert reopened.replay_speed_index == 2
    assert not reopened.sound_enabled
    assert not sound.is_enabled()
    reopened.progress_store.close()
    pygame.quit()


def test_home_routes_to_categorized_lesson_libraries():
    ui = ChessUI(":memory:")
    ui._build_menu_buttons()
    labels = [button.label for button in ui._menu_buttons]
    assert labels[:3] == ["Learn", "Play", "Watch games"]
    next(button for button in ui._menu_buttons
         if button.label == "Learn").action()
    ui._build_menu_buttons()
    labels = [button.label for button in ui._menu_buttons]
    assert "Guided games" in labels
    assert "Openings" in labels
    assert "Endgames" in labels
    assert "Your lesson path" in labels
    assert not any("difficulty" in label.lower() for label in labels)

    ui._open_menu_section("play")
    ui._build_menu_buttons()
    assert not any("AI DIFFICULTY" in head[0] for head in ui._menu_heads)
    next(button for button in ui._menu_buttons
         if button.label == "Play against AI").action()
    ui._build_menu_buttons()
    assert any("AI DIFFICULTY" in head[0] for head in ui._menu_heads)

    ui._open_menu_section("main")
    ui._build_menu_buttons()

    next(button for button in ui._menu_buttons
         if button.label == "Watch games").action()
    assert ui.library_filter == "replay"
    ui._build_menu_buttons()
    replay_labels = [button.label for button in ui._menu_buttons]
    assert "Tactical coordination study" in replay_labels
    assert "Make your pieces work together" not in replay_labels

    ui._open_library("endgame")
    ui._build_menu_buttons()
    endgame_labels = [button.label for button in ui._menu_buttons]
    assert "Finish without stalemate" in endgame_labels
    assert "Promote with enough power" in endgame_labels
    assert "Start with a useful plan" not in endgame_labels
    assert "Opposition and king activity" not in endgame_labels

    ui._on_key(pygame.K_PAGEDOWN)
    ui._build_menu_buttons()
    second_page_labels = [button.label for button in ui._menu_buttons]
    assert ui.library_page == 1
    assert "Step around the blocking king" in second_page_labels
    assert "Finish without stalemate" not in second_page_labels

    ui._on_key(pygame.K_PAGEUP)
    assert ui.library_page == 0

    ui._open_library("opening")
    ui._build_menu_buttons()
    opening_labels = [button.label for button in ui._menu_buttons]
    assert "Start with a useful plan" in opening_labels
    assert "Make room in centre" in opening_labels
    ui._on_key(pygame.K_PAGEDOWN)
    ui._build_menu_buttons()
    assert "Italian Game: develop, castle, break" in [
        button.label for button in ui._menu_buttons]
    assert "Finish without stalemate" not in opening_labels
    ui.progress_store.close()
    pygame.quit()


def test_course_source_replay_returns_to_about_and_browse_restores(tmp_path):
    path = tmp_path / "progress.sqlite3"
    ui = ChessUI(path)
    ui._on_resize(420, 720)
    course = ui.game_library.courses[0]
    ui._open_course(course.course_id)
    ui._build_menu_buttons()
    assert all(ui.screen.get_rect().contains(button.rect)
               for button in ui._menu_buttons)
    assert any(button.label == "Sources"
               for button in ui._menu_buttons)
    ui._open_course_about()
    for width, height in ((420, 720), (360, 700), (360, 640)):
        ui._on_resize(width, height)
        for scale in (1.0, 1.2, 1.4):
            ui._set_text_scale(scale)
            ui._menu_buttons = []
            ui._draw()
            assert all(ui.screen.get_rect().contains(button.rect)
                       for button in ui._menu_buttons)
    ui._watch_course_source()
    assert ui.replay_entry.game.game_id == course.source_game_id
    ui._leave_replay()
    assert ui.menu_view == "course_about"
    ui.progress_store.close()
    pygame.quit()

    reopened = ChessUI(path)
    reopened._open_menu_section("learn")
    reopened._build_menu_buttons()
    assert any(button.label == "Return to last course or list"
               for button in reopened._menu_buttons)
    reopened._restore_learn_browse()
    assert reopened.menu_view == "course"
    assert reopened.active_course_id == course.course_id
    reopened.progress_store.close()
    pygame.quit()


def test_opening_list_lesson_returns_to_same_list_page():
    ui = ChessUI(":memory:")
    ui._open_library("opening")
    ui._change_library_page(1)
    selected_page = ui.library_page
    entry = ui.game_library.lesson_entry("olive-catalan-bishop")
    ui.start_lesson(entry)
    ui._leave_lesson()
    assert ui.menu_view == "library"
    assert ui.library_filter == "opening"
    assert ui.library_page == selected_page
    ui.progress_store.close()
    pygame.quit()


def test_learning_list_page_survives_repeated_restarts(tmp_path):
    path = tmp_path / "browse.sqlite3"
    ui = ChessUI(path)
    ui._open_menu_section("learn")
    ui._open_library("opening")
    ui._change_library_page(1)
    assert ui.library_page == 1
    ui.progress_store.close()
    pygame.quit()

    for _ in range(2):
        ui = ChessUI(path)
        ui._open_menu_section("learn")
        ui._restore_learn_browse()
        assert (ui.menu_view, ui.library_filter, ui.library_page) == (
            "library", "opening", 1)
        assert ui.progress_store.load_settings()["last_learn_browse"]["page"] == 1
        ui.progress_store.close()
        pygame.quit()

    ui = ChessUI(path)
    ui._open_library("opening", page=999)
    assert ui.library_page == 2
    assert ui.progress_store.load_settings()["last_learn_browse"]["page"] == 2
    ui.progress_store.close()
    pygame.quit()


def test_every_published_course_page_is_reachable_with_keys_and_mouse():
    ui = ChessUI(":memory:")
    source = ui.game_library.courses[0]
    original = ui.game_library
    for count in (0, 1, 5):
        courses = tuple(replace(source, course_id="fixture-{}".format(i),
                                title="Player {}".format(i))
                        for i in range(count))
        ui.game_library = replace(original, courses=courses)
        ui._on_resize(360, 600)
        ui._set_text_scale(1.4)
        ui._open_openings()
        seen = set()
        for page in range(max(1, (count + 1) // 2)):
            ui._build_menu_buttons()
            cards = [button for button in ui._menu_buttons
                     if button.kind == "player"]
            assert all(ui.screen.get_rect().contains(button.rect)
                       for button in ui._menu_buttons)
            seen.update(button.value for button in cards)
            if page < (count - 1) // 2:
                ui._on_key(pygame.K_PAGEDOWN)
        assert seen == {course.course_id for course in courses}
        if count == 5:
            card = cards[0]
            ui._on_mouse_down(card.rect.center)
            assert ui.active_course_id == card.value
            ui._open_menu_section("opening_hub")
            assert ui.course_page == 2
    ui.progress_store.close()
    pygame.quit()


def test_course_prerequisites_offer_basics_and_return_to_chosen_player():
    ui = ChessUI(":memory:")
    course = ui.game_library.courses[0]
    ui._open_course(course.course_id)
    ui._build_menu_buttons()
    basics = next(button for button in ui._menu_buttons
                  if button.label == "Practise basics")
    basics.action()
    assert ui.lesson.lesson.lesson_id == "opening-essentials"
    ui._leave_lesson()
    assert (ui.menu_view, ui.active_course_id) == ("course", course.course_id)

    opening = ui.game_library.lesson_entry("opening-essentials")
    ui.start_lesson(opening)
    for _ in opening.lesson.steps:
        ui._lesson_reveal()
        ui._lesson_continue()
    ui._leave_lesson()
    ui._open_course(course.course_id)
    ui._build_menu_buttons()
    assert not any(button.label == "Practise basics"
                   for button in ui._menu_buttons)

    ui.progress_store.close()
    ui.progress_store = None
    ui._build_menu_buttons()
    assert any(button.label == "Practise basics"
               for button in ui._menu_buttons)
    pygame.quit()


def test_menu_and_library_render_at_every_text_size():
    ui = ChessUI(":memory:")
    screen = ui.screen.get_rect()
    for scale in (1.0, 1.2, 1.4):
        ui._set_text_scale(scale)
        ui.menu_view = "main"
        ui._menu_buttons = []
        ui._draw()
        assert all(screen.contains(button.rect) for button in ui._menu_buttons)

        ui._open_library("endgame")
        for page in (0, 1):
            ui.library_page = page
            ui._menu_buttons = []
            ui._draw()
            assert all(screen.contains(button.rect)
                       for button in ui._menu_buttons)

        ui._open_colors()
        ui._draw()
        assert all(screen.contains(button.rect) for button in ui._menu_buttons)
    ui.progress_store.close()
    pygame.quit()


def test_lesson_question_and_feedback_have_clear_controls():
    ui = ChessUI(":memory:")
    ui._on_resize(1100, 760)
    ui.start_lesson(ui.game_library.lesson_entry("bruno-scotch-make-room"),
                    course_id="bruno-scotch-first-ideas")
    ui._build_lesson_buttons()
    assert [button.label for button in ui._game_buttons] == [
        "Hint", "Show answer", "Lessons", "Main menu"]
    ui._draw()
    assert ui.study_view.lesson_content_rect.h < 150
    assert ui.study_view.question_rect.bottom <= ui.study_view.lesson_content_rect.top

    ui._lesson_hint()
    assert coach_advice(ui.lesson, ui.lesson_message) != ui.lesson_message
    ui._lesson_reveal()
    ui._build_lesson_buttons()
    assert [button.label for button in ui._game_buttons] == [
        "Finish lesson", "Try other move", "Lessons", "Main menu"]
    assert ui._game_buttons[0].kind == "cta"
    ui._draw()
    assert ui.study_view.lesson_content_rect.bottom <= ui._game_buttons[0].rect.top
    ui.progress_store.close()
    pygame.quit()


def test_portrait_click_changes_player_and_completes_animation():
    ui = ChessUI(":memory:")
    ui._draw()
    assert ui._portrait_hit_rect == ui._feature_rect
    assert ui._portrait_hit_rect.bottom < ui._menu_card.top
    assert ui._portrait_hit_rect.centerx == ui._menu_card.centerx
    first = ui.chess_thought
    ui._on_mouse_down(ui._portrait_hit_rect.center)
    assert ui.chess_thought != first
    assert ui.chess_thought.portrait != first.portrait
    assert ui._thought_previous == first
    assert ui._thought_progress() < 1.0
    ui._draw()
    ui._thought_changed_at -= ui._thought_duration
    ui._draw()
    assert ui._thought_previous is None

    entry = next(entry for entry in ui.game_library.entries
                 if entry.game.game_id == "coordination-study")
    ui.start_replay(entry)
    ui._draw()
    assert ui._portrait_hit_rect is not None
    assert ui._portrait_hit_rect.top == ui.panel_y + 14
    first = ui.chess_thought
    ui._on_mouse_down(ui._portrait_hit_rect.center)
    assert ui.chess_thought != first

    ui.start_lesson(entry)
    ui._draw()
    assert ui._portrait_hit_rect is not None
    assert ui._portrait_hit_rect.top == ui.panel_y + 14
    assert ui._portrait_hit_rect.left >= ui.panel_x
    first = ui.chess_thought
    ui._on_mouse_down(ui._portrait_hit_rect.center)
    assert ui.chess_thought != first

    ui._on_resize(700, 700)
    ui._build_lesson_buttons()
    ui._draw()
    assert ui._portrait_hit_rect == ui._board_thought_rect
    assert ui._portrait_hit_rect.bottom < ui.board_y
    first = ui.chess_thought
    ui._on_mouse_down(ui._portrait_hit_rect.center)
    assert ui.chess_thought != first
    ui.progress_store.close()
    pygame.quit()


def test_portrait_is_present_on_every_menu_and_play_layout():
    ui = ChessUI(":memory:")
    ui._draw()
    assert ui._menu_card.top == 225
    assert ui._feature_rect.top >= 85
    assert ui._menu_card.top - ui._feature_rect.bottom >= 40
    for size in ((700, 700), (650, 650), (600, 600)):
        ui._on_resize(*size)
        ui._build_menu_buttons()
        assert all(ui.screen.get_rect().contains(button.rect)
                   for button in ui._menu_buttons)
    ui._on_resize(980, 760)
    ui._build_menu_buttons()

    for open_view in (lambda: ui._open_library("opening"), ui._open_colors):
        open_view()
        ui._draw()
        assert ui._portrait_hit_rect == ui._feature_rect
        assert ui._feature_rect.bottom < ui._menu_card.top
        first = ui.chess_thought
        ui._on_mouse_down(ui._portrait_hit_rect.center)
        assert ui.chess_thought != first

    ui.start_game({"w"})
    ui._draw()
    assert ui._portrait_hit_rect is not None
    assert ui._portrait_hit_rect.left >= ui.panel_x
    assert ui._portrait_hit_rect.top == ui.panel_y + 16
    first = ui.chess_thought
    ui._on_mouse_down(ui._portrait_hit_rect.center)
    assert ui.chess_thought != first

    ui._on_resize(640, 700)
    ui._build_game_buttons()
    ui._draw()
    assert ui._portrait_hit_rect == ui._board_thought_rect
    assert ui._portrait_hit_rect.bottom < ui.board_y

    entry = next(entry for entry in ui.game_library.entries
                 if entry.game.game_id == "coordination-study")
    ui.start_replay(entry)
    ui._draw()
    assert ui._portrait_hit_rect == ui._board_thought_rect
    ui._on_resize(980, 760)
    ui._build_replay_buttons()
    ui._draw()
    assert ui._portrait_hit_rect.left >= ui.panel_x
    assert ui._portrait_hit_rect.top == ui.panel_y + 14
    ui.progress_store.close()
    pygame.quit()


def test_portrait_changes_on_navigation_and_lesson_has_main_menu_shortcut():
    ui = ChessUI(":memory:")
    first = ui.chess_thought
    ui._draw()
    assert ui.chess_thought == first
    ui._on_resize(700, 700)
    ui._draw()
    assert ui.chess_thought == first
    ui._open_library("endgame")
    assert ui.chess_thought != first
    first = ui.chess_thought
    ui._draw()
    assert ui.chess_thought == first
    ui._change_library_page(1)
    assert ui.chess_thought != first

    entry = next(entry for entry in ui.game_library.entries
                 if entry.game.game_id == "coordination-study")
    first = ui.chess_thought
    ui.start_lesson(entry)
    assert ui.chess_thought != first
    ui._build_lesson_buttons()
    assert "Menu" in [button.label for button in ui._game_buttons]
    first = ui.chess_thought
    ui._on_key(pygame.K_m)
    assert (ui.scene, ui.menu_view) == ("menu", "main")
    assert ui.chess_thought != first

    ui.start_lesson(entry)
    ui._build_lesson_buttons()
    next(button for button in ui._game_buttons
         if button.label == "Menu").action()
    assert (ui.scene, ui.menu_view) == ("menu", "main")
    ui.progress_store.close()
    pygame.quit()


def test_replay_library_text_stays_inside_its_buttons():
    ui = ChessUI(":memory:")
    for scale in (1.0, 1.2, 1.4):
        ui._set_text_scale(scale)
        ui._open_library("replay")
        ui._build_menu_buttons()
        entries = [button for button in ui._menu_buttons
                   if button.kind == "library"]
        assert entries
        for button in entries:
            ui._draw_menu_button(button, False, 8)
            width = button.rect.w - 28
            title = _fit_text(ui.text_font, button.label, width)
            assert ui.text_font.size(title)[0] <= width
            lines = _wrap_text(ui.small_font, button.detail, width)
            assert len(lines) == 1
            assert ui.small_font.size(lines[0])[0] <= width
        ui._draw()
    ui._on_resize(360, 700)
    ui._build_menu_buttons()
    ui._draw()
    assert ui.screen.get_rect().contains(ui._menu_card)
    assert all(ui.screen.get_rect().contains(button.rect)
               for button in ui._menu_buttons)
    ui.progress_store.close()
    pygame.quit()


def test_narrow_screens_keep_appearance_replay_and_question_visible():
    ui = ChessUI(":memory:")
    replay = next(entry for entry in ui.game_library.entries
                  if entry.game.game_id == "coordination-study")
    for size in ((420, 720), (360, 700), (600, 600)):
        ui._on_resize(*size)
        for scale in (1.0, 1.2, 1.4):
            ui._set_text_scale(scale)
            ui._open_colors()
            ui._draw()
            assert ui.screen.get_rect().contains(ui._menu_card)
            assert all(ui.screen.get_rect().contains(button.rect)
                       for button in ui._menu_buttons)
            assert ui.screen.get_rect().contains(ui._preview_rect)

            ui.start_replay(replay)
            ui._build_replay_buttons()
            ui._draw()
            panel = pygame.Rect(ui.panel_x, ui.panel_y,
                                ui.panel_w, ui.panel_h)
            assert ui.show_panel and ui.screen.get_rect().contains(panel)
            assert all(panel.contains(button.rect)
                       for button in ui._game_buttons)
            labels = {button.label for button in ui._game_buttons}
            assert "Back" in labels
            assert ("Prev" if ui.panel_w < 280 else "‹  Previous") in labels
            assert ("Next" if ui.panel_w < 280 else "Next  ›") in labels

            ui.start_lesson(replay)
            ui._build_lesson_buttons()
            ui._draw()
            question = ui.study_view.question_rect
            content = ui.study_view.lesson_content_rect
            provenance = ui.study_view.provenance_rect
            button_top = min(button.rect.y for button in ui._game_buttons)
            assert question is not None
            assert panel.contains(provenance)
            assert provenance.bottom <= question.top
            assert panel.contains(question)
            assert question.bottom <= content.top < content.bottom <= button_top
            assert all(ui.screen.get_rect().contains(button.rect)
                       for button in ui._game_buttons)
            ui._to_menu()
    ui.progress_store.close()
    pygame.quit()


def test_short_study_menus_keep_navigation_visible_at_all_text_sizes():
    ui = ChessUI(":memory:")
    course_id = ui.game_library.courses[0].course_id
    for width in (360, 420, 600):
        ui._on_resize(width, 600)
        for scale in (1.0, 1.2, 1.4):
            ui._set_text_scale(scale)
            for view in ("opening_hub", "course", "course_about", "library"):
                ui.menu_view = view
                ui.active_course_id = course_id
                ui.library_filter = "opening"
                ui.library_page = 1
                ui._build_menu_buttons()
                screen = ui.screen.get_rect()
                assert screen.contains(ui._menu_card)
                assert all(screen.contains(button.rect)
                           for button in ui._menu_buttons)
                if view == "library":
                    for button in ui._menu_buttons[-3:]:
                        assert ui.small_font.size(button.label)[0] <= button.rect.w - 12
                ui._draw()
    ui.progress_store.close()
    pygame.quit()


def test_old_ai_search_cannot_move_in_a_new_game(monkeypatch):
    started = threading.Event()
    release = threading.Event()

    def delayed_search(board, **_kwargs):
        started.set()
        assert release.wait(2)
        return legal_moves(board)[0], 0, (), 1

    monkeypatch.setattr("chess_game.ui.ai.analyse", delayed_search)
    ui = ChessUI(":memory:")
    ui.start_game(set())
    assert started.wait(2)
    old_queue = ui.ai_queue
    ui.start_game({"w"})
    release.set()
    assert old_queue.get(timeout=2)[2] is None
    assert not ui._poll_ai()
    assert not ui.moves
    assert ui.board.side_to_move == "w"
    ui.progress_store.close()
    pygame.quit()


def test_ai_search_error_clears_thinking_without_moving(monkeypatch):
    def failed_search(_board, **_kwargs):
        raise RuntimeError("search stopped")

    monkeypatch.setattr("chess_game.ui.ai.analyse", failed_search)
    ui = ChessUI(":memory:")
    ui.start_game(set())
    deadline = time.monotonic() + 2
    while ui.thinking and time.monotonic() < deadline:
        ui._poll_ai()
        time.sleep(0.001)
    assert not ui.thinking
    assert not ui.moves
    assert "search stopped" in ui.toast
    ui.progress_store.close()
    pygame.quit()


def test_first_lesson_move_tip_disappears_after_selecting_a_piece(tmp_path):
    path = tmp_path / "progress.sqlite3"
    ui = ChessUI(path)
    entry = ui._path_entries()[0]
    ui.start_lesson(entry)
    assert not ui.move_hint_seen
    ui._select((6, 4))  # White's e-pawn can move in the opening position.
    assert ui.move_hint_seen
    ui.progress_store.close()
    pygame.quit()

    reopened = ChessUI(path)
    assert reopened.move_hint_seen
    reopened.progress_store.close()
    pygame.quit()


def test_player_opening_route_keeps_coach_and_question_visible(tmp_path):
    from chess_game.study import ChessAdapter

    path = tmp_path / "player-progress.sqlite3"
    ui = ChessUI(path)
    ui._open_menu_section("learn")
    ui._build_menu_buttons()
    next(button for button in ui._menu_buttons
         if button.label == "Openings").action()
    ui._build_menu_buttons()
    assert ui.menu_view == "opening_hub"
    player_card = next(button for button in ui._menu_buttons
                       if button.kind == "player")
    ui._on_mouse_down(player_card.rect.center)
    ui._build_menu_buttons()
    assert ui.menu_view == "course"
    while ui._button_focus is None or ui._menu_buttons[ui._button_focus].kind != "library":
        ui._on_key(pygame.K_TAB)
    ui._on_key(pygame.K_RETURN)
    assert ui.coach_profile.player_id == "bruno-bear"
    assert ui.lesson_course_id == "bruno-scotch-first-ideas"
    original_portrait = ui.coach_profile.portrait
    ui._build_lesson_buttons()
    ui._draw()
    ui._on_key(pygame.K_n)
    assert ui.coach_profile.portrait == original_portrait
    assert ui.lesson.hints_used == 0
    move = ChessAdapter.resolve_uci(ui.board, "d2d4")
    ui._apply_lesson_move(move)
    assert "Which knight" in ui.lesson.active_prompt
    for size in ((980, 760), (420, 720), (360, 700),
                 (600, 600), (819, 760), (821, 760)):
        ui._on_resize(*size)
        for scale in (1.0, 1.2, 1.4):
            ui._set_text_scale(scale)
            ui._build_lesson_buttons()
            ui._draw()
            question = ui.study_view.question_rect
            assert question is not None
            assert question.bottom <= min(button.rect.y
                                          for button in ui._game_buttons)
            assert ui.study_view.lesson_content_rect.height >= 20
            assert ui._portrait_hit_rect is not None
    ui._on_mouse_down(ui._portrait_hit_rect.center)
    assert ui.lesson.hints_used == 0
    ui._leave_lesson()
    assert ui.menu_view == "course"
    ui.progress_store.close()
    pygame.quit()

    reopened = ChessUI(path)
    reopened._continue_learning()
    assert reopened.lesson.lesson.lesson_id == "bruno-scotch-make-room"
    assert reopened.coach_profile.player_id == "bruno-bear"
    reopened.progress_store.close()
    pygame.quit()


def test_olive_course_next_resume_and_independent_revisit(tmp_path):
    from chess_game.study import ChessAdapter, COMPLETED

    path = tmp_path / "olive-progress.sqlite3"
    ui = ChessUI(path)
    ui._on_resize(360, 700)
    ui._set_text_scale(1.4)
    ui._open_openings()
    ui._build_menu_buttons()
    assert len([button for button in ui._menu_buttons
                if button.kind == "player"]) == 2
    card = next(button for button in ui._menu_buttons
                if button.value == "olive-catalan-first-ideas")
    ui._on_mouse_down(card.rect.center)
    ui._build_menu_buttons()
    assert ui.menu_view == "course"
    course = ui.game_library.course(ui.active_course_id)
    entries = ui.game_library.course_lessons(course)
    assert [ui._course_entry_status(entry) for entry in entries] == [
        "NEXT", "LATER", "LATER"]

    ui.start_lesson(entries[0], course_id=course.course_id)
    assert ui.coach_profile.player_id == "olive-owl"
    ui._apply_lesson_move(ChessAdapter.resolve_uci(ui.board, "f1g2"))
    ui._lesson_continue()
    assert ui.lesson.state == COMPLETED
    assert ui._next_path_entry() == entries[1]
    ui._lesson_next()
    assert ui.lesson_entry == entries[1]
    ui._to_menu()
    ui.progress_store.close()
    pygame.quit()

    resumed = ChessUI(path)
    resumed._continue_learning()
    assert resumed.lesson_entry.lesson.lesson_id == entries[1].lesson.lesson_id
    assert resumed.coach_profile.player_id == "olive-owl"
    resumed._apply_lesson_move(ChessAdapter.resolve_uci(resumed.board, "e1g1"))
    resumed._lesson_continue()
    resumed._lesson_next()
    assert resumed.lesson_entry == entries[2]
    assert resumed.lesson.current_step.practice_mode == "independent"
    assert not resumed.lesson.visible_highlights
    resumed._lesson_hint()
    resumed._apply_lesson_move(ChessAdapter.resolve_uci(resumed.board, "f1g2"))
    resumed._lesson_continue()
    resumed._leave_lesson()
    assert resumed.menu_view == "course"
    assert resumed._course_entry_status(entries[2]) == "REVISIT"
    assert resumed._course_progress(course) == "3 of 3 lessons done"
    resumed._build_menu_buttons()
    assert any(button.label in ("Review", "Review last lesson")
               for button in resumed._menu_buttons)
    resumed._draw()
    resumed.progress_store.close()
    pygame.quit()

def test_portrait_and_card_use_active_theme_colors():
    pygame.init()
    pygame.display.set_mode((1, 1))
    title = pygame.font.Font(None, 20)
    body = pygame.font.Font(None, 16)
    small = pygame.font.Font(None, 13)
    dark = SimpleNamespace(field=(20, 28, 38), text=(230, 225, 210),
                           panel_line=(90, 100, 120), accent=(150, 190, 255))
    light = SimpleNamespace(field=(245, 235, 215), text=(35, 30, 25),
                            panel_line=(120, 110, 100), accent=(80, 45, 120))
    surfaces = []
    for palette in (dark, light):
        surface = pygame.Surface((240, 100))
        draw_chess_thought(surface, (0, 0, 240, 100), THOUGHTS[0],
                           title, body, small, palette, compact=True)
        assert surface.get_at((8, 8))[:3] == palette.field
        surfaces.append(pygame.image.tobytes(surface, "RGB"))
    assert surfaces[0] != surfaces[1]

    frames = []
    for progress in (0.0, 0.5, 1.0):
        surface = pygame.Surface((240, 100))
        draw_chess_thought(surface, (0, 0, 240, 100), THOUGHTS[1],
                           title, body, small, dark, compact=True,
                           previous=THOUGHTS[0], progress=progress)
        frames.append(pygame.image.tobytes(surface, "RGB"))
    assert len(set(frames)) == 3
    pygame.quit()
