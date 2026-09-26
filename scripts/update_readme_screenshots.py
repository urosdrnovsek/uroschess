"""Capture the README screens with pygame's headless video driver."""

import os
import random
import struct
import zlib
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from chess_game.pieces import WHITE
from chess_game.ui import ChessUI


DOCS = Path(__file__).resolve().parents[1] / "docs"


def _chunk(kind, data):
    return (struct.pack(">I", len(data)) + kind + data +
            struct.pack(">I", zlib.crc32(kind + data) & 0xffffffff))


def save_png(surface, path):
    """Write an RGB PNG using only the Python standard library."""
    width, height = surface.get_size()
    pixels = pygame.image.tobytes(surface, "RGB")
    stride = width * 3
    rows = b"".join(b"\0" + pixels[y * stride:(y + 1) * stride]
                    for y in range(height))
    data = (b"\x89PNG\r\n\x1a\n" +
            _chunk(b"IHDR", struct.pack(">IIBBBBB", width, height,
                                         8, 2, 0, 0, 0)) +
            _chunk(b"IDAT", zlib.compress(rows, 9)) +
            _chunk(b"IEND", b""))
    path.write_bytes(data)


def capture(ui, name):
    ui._thought_changed_at -= ui._thought_duration
    if ui.scene == "menu":
        ui._build_menu_buttons()
    elif ui.scene == "lesson":
        ui._build_lesson_buttons()
    elif ui.scene == "replay":
        ui._build_replay_buttons()
    else:
        ui._build_game_buttons()
    ui._draw()
    path = DOCS / name
    save_png(ui.screen, path)
    print("saved", path.relative_to(DOCS.parent))


def main():
    random.seed(7)
    ui = ChessUI(":memory:")
    try:
        capture(ui, "menu.png")
        ui._open_menu_section("learn")
        capture(ui, "learn.png")
        ui._open_colors()
        capture(ui, "colours.png")
        ui.start_game({WHITE})
        capture(ui, "game.png")
        ui._on_resize(420, 720)
        ui.start_lesson(ui._path_entries()[0])
        capture(ui, "lesson-narrow.png")
        replay = next(entry for entry in ui.game_library.entries
                      if entry.game.game_id == "coordination-study")
        ui.start_replay(replay)
        capture(ui, "replay-narrow.png")
        ui._to_menu()
        ui._open_menu_section("learn")
        ui._open_openings()
        capture(ui, "openings.png")
        ui._open_course("olive-catalan-first-ideas")
        capture(ui, "olive-course.png")
        ui._open_course_about()
        capture(ui, "course-sources.png")
        ui._open_menu_section("course")
        ui.start_lesson(ui.game_library.lesson_entry(
            "olive-catalan-bishop"),
            course_id="olive-catalan-first-ideas")
        capture(ui, "olive-lesson.png")
        ui._leave_lesson()
        ui._open_menu_section("opening_hub")
        ui._open_course("bruno-scotch-first-ideas")
        capture(ui, "bruno-course.png")
        ui.start_lesson(ui.game_library.lesson_entry(
            "bruno-scotch-make-room"),
            course_id="bruno-scotch-first-ideas")
        capture(ui, "bruno-lesson.png")
        ui._on_resize(1100, 760)
        capture(ui, "lesson-wide.png")
    finally:
        if ui.progress_store is not None:
            ui.progress_store.close()
        pygame.quit()


if __name__ == "__main__":
    main()
