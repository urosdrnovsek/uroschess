"""Audit desktop layouts with isolated progress and save reproducible captures.

Run with ``python -m scripts.audit_usability --output /tmp/uroschess-usability``.
This is an internal geometry/rendering audit, not a learner observation.
"""

import argparse
from collections import Counter
import json
import os
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from chess_game.challenge import ROSTER
from chess_game.study import ChessAdapter, LessonController
from chess_game.ui import ChessUI
from .update_readme_screenshots import save_png


SIZES = ((360, 320), (420, 720), (719, 600),
         (720, 480), (819, 600), (820, 600), (980, 760))
SCALES = (1.0, 1.2, 1.4)
STATE_LESSONS = {"chicky-knight-steps", "pippa-castle-white", "tina-first-promotion",
                 "tom-remove-attacker", "bruno-double-rooks", "olivia-rook-skewer",
                 "monty-amsterdam-analysis"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path,
                        default=Path("/tmp/uroschess-usability"))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    ui = ChessUI(":memory:")
    issues, counts = [], Counter()

    def check(condition, message, context):
        if not condition:
            issues.append(dict(context, problem=message))

    def inspect(context):
        counts[context["scene"]] += 1
        buttons = ui._menu_buttons if ui.scene == "menu" else ui._game_buttons
        window = ui.screen.get_rect()
        for index, button in enumerate(buttons):
            check(window.contains(button.rect), "control outside window: " + button.label,
                  context)
            check(not any(button.rect.colliderect(other.rect)
                          for other in buttons[index + 1:]),
                  "overlapping control: " + button.label, context)
        if ui.scene == "menu":
            return
        board = pygame.Rect(ui.board_x - ui.frame, ui.board_y - ui.frame,
                            ui.board_px + 2 * ui.frame, ui.board_px + 2 * ui.frame)
        status = pygame.Rect(ui.status_x, ui.status_y, ui.status_w, ui.status_h)
        check(window.contains(board), "board outside window", context)
        check(window.contains(status), "status outside window", context)
        check(not board.colliderect(status), "board overlaps status", context)
        check(ui.SQ >= 24, "board squares smaller than 24 pixels", context)
        for button in buttons:
            check(not board.colliderect(button.rect), "board overlaps control", context)
        if ui.scene == "lesson":
            panel = pygame.Rect(ui.panel_x, ui.panel_y, ui.panel_w, ui.panel_h)
            question = ui.study_view.question_rect
            content = ui.study_view.lesson_content_rect
            top = min(b.rect.top for b in buttons if not b.kind.startswith("lesson_nav"))
            check(panel.contains(content) and content.bottom <= top,
                  "feedback outside reading area", context)
            check(content.h >= 40, "feedback area smaller than 40 pixels", context)
            if question:
                check(panel.contains(question) and question.bottom <= content.top,
                      "question overlaps feedback or controls", context)
        elif ui.scene == "replay":
            notes = ui.study_view.replay_note_rect
            moves = ui.study_view.replay_moves_rect
            top = min(button.rect.top for button in buttons)
            check(notes.bottom <= moves.top and moves.bottom <= top,
                  "replay notes or moves overlap controls", context)

    def draw(context, capture=None):
        if ui.scene == "menu":
            ui._build_menu_buttons()
        elif ui.scene == "lesson":
            ui._build_lesson_buttons()
        elif ui.scene == "replay":
            ui._build_replay_buttons()
        else:
            ui._build_game_buttons()
        ui._draw()
        inspect(context)
        if capture:
            save_png(ui.screen, args.output / (capture + ".png"))

    try:
        # Unlock only this in-memory profile so Monty's layouts are also audited.
        ui.collection_counts["monty-cat"] = 1
        for size in SIZES:
            ui._on_resize(*size)
            for scale in SCALES:
                ui._set_text_scale(scale)
                context = {"requested_size": size, "actual_size": ui.screen.get_size(),
                           "text_scale": scale}
                capture = size in ((360, 320), (980, 760)) and scale == 1.4
                for entry in ui.game_library.lesson_entries:
                    ui.collection_counts["monty-cat"] = 1
                    ui.start_lesson(entry)
                    assert ui.scene == "lesson" and ui.lesson_entry == entry
                    for index in range(len(entry.lesson.steps)):
                        # No persisted completion can hide a question on later passes.
                        ui.lesson = LessonController(entry.game, entry.lesson,
                                                     resume_step=index)
                        if ui.lesson.current_step.question:
                            ui.lesson.begin_question()
                        ui.lesson_message = ""
                        ui._sync_lesson_position()
                        lesson_context = dict(context, scene="lesson",
                                              lesson=entry.lesson.lesson_id, step=index)
                        draw(lesson_context, ("lesson-{}-{}".format(size[0], index)
                             if capture and entry.lesson.lesson_id == "chicky-knight-steps"
                             else None))
                    if entry.lesson.lesson_id in STATE_LESSONS:
                        ui.lesson = LessonController(entry.game, entry.lesson)
                        ui.lesson.begin_question()
                        ui._sync_lesson_position()
                        for state, action in (("hint", ui._lesson_hint),
                                              ("answer", ui._lesson_reveal),
                                              ("exploration", ui._lesson_begin_exploration),
                                              ("return", ui._lesson_return),
                                              ("restart", ui._lesson_restart)):
                            action()
                            draw(dict(context, scene="lesson", lesson=entry.lesson.lesson_id,
                                      state=state),
                                 "{}-{}".format(state, size[0]) if capture and
                                 entry.lesson.lesson_id == "chicky-knight-steps" else None)
                        wrong = next((node.uci for node in ui.lesson.current_step.question.tree
                                      if node.outcome in ("wrong", "off_goal")), None)
                        if wrong:
                            ui._apply_lesson_move(ChessAdapter.resolve_uci(ui.board, wrong))
                            draw(dict(context, scene="lesson", lesson=entry.lesson.lesson_id,
                                      state="wrong_move"))
                            if ui.lesson.state == "FEEDBACK":
                                ui._lesson_retry()
                        while ui.lesson.state != "COMPLETED":
                            ui._lesson_reveal()
                            ui._lesson_continue()
                        draw(dict(context, scene="lesson", lesson=entry.lesson.lesson_id,
                                  state="completed"),
                             "completed-{}".format(size[0]) if capture and
                             entry.lesson.lesson_id == "chicky-knight-steps" else None)
                ui._to_menu()
                for view in ("main", "learn", "play", "ai_play", "characters", "colors"):
                    ui._open_menu_section(view)
                    draw(dict(context, scene="menu", view=view))
                for opponent in ROSTER:
                    ui._open_guide_lessons(opponent.ident)
                    for page in range(len(ui._guide_entries(opponent.ident))):
                        ui.guide_lesson_page = page
                        draw(dict(context, scene="menu", view="guide_lessons",
                                  guide=opponent.ident, page=page))
                        if ui.guide_lesson_page < page:
                            break
                for course in ui.game_library.courses:
                    ui._open_course(course.course_id)
                    for page in range(len(course.lesson_ids)):
                        ui.course_lesson_page = page
                        draw(dict(context, scene="menu", view="course",
                                  course=course.course_id, page=page))
                        if ui.course_lesson_page < page:
                            break
                    if course.source_game_id and course.association_source:
                        ui._open_course_about()
                        draw(dict(context, scene="menu", view="course_about",
                                  course=course.course_id))
                for category in ("path", "opening", "endgame", "replay", "guided_game"):
                    ui._open_library(category)
                    for page in range(1 + len(ui._library_entries()) // 5):
                        ui.library_page = page
                        draw(dict(context, scene="menu", view="library",
                                  category=category, page=page))
                ui._open_collection()
                draw(dict(context, scene="menu", view="collection"))
                ui._open_challenge_menu()
                for page in range(2):
                    ui.challenge_page = page
                    draw(dict(context, scene="menu", view="challenge", page=page))
                ui._choose_challenge_opponent("chicky")
                draw(dict(context, scene="menu", view="challenge_color"))
                ui._open_challenge_archive()
                draw(dict(context, scene="menu", view="challenge_archive"))
                ui.start_game({"w", "b"})
                draw(dict(context, scene="game"),
                     "game-{}".format(size[0]) if capture else None)
                ui._to_menu()
                print("Checked {} at text scale {}".format(ui.screen.get_size(), scale),
                      flush=True)
                ui._start_challenge("w", "chicky")
                assert ui.challenge is not None
                draw(dict(context, scene="challenge"),
                     "challenge-{}".format(size[0]) if capture else None)
                match_id = ui.challenge.match_id
                ui._to_menu()
                ui.challenge_store.discard(match_id)
                ui.start_replay(ui.game_library.entries[0])
                draw(dict(context, scene="replay"),
                     "replay-{}".format(size[0]) if capture else None)
                ui._to_menu()
    finally:
        ui._cancel_challenge_search()
        ui.progress_store.close()
        pygame.quit()
    report = {"kind": "internal automated usability audit; no learner observations",
              "screens_checked": dict(counts), "total": sum(counts.values()),
              "issues": issues}
    (args.output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"screens_checked": dict(counts), "issues": len(issues),
                      "report": str(args.output / "report.json")}))
    if issues:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
