"""Milestone 0 checks for study models, adapter, and reusable board view."""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from chess_game.study import ChessAdapter, GameRecord, Lesson, LessonStep, MoveNode
from chess_game.views import BoardView


def test_adapter_replays_uci_and_reports_san():
    board, moves, sans = ChessAdapter.replay(
        ("e2e4", "e7e5", "g1f3", "b8c6"))
    assert tuple(str(move) for move in moves) == (
        "e2e4", "e7e5", "g1f3", "b8c6")
    assert sans == ("e4", "e5", "Nf3", "Nc6")
    assert ChessAdapter.fen(board) == (
        "r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/"
        "RNBQKB1R w KQkq - 2 3")


def test_study_models_validate_identity_and_freeze_headers():
    root = MoveNode(children=(MoveNode(uci="e2e4", comment="Controls the centre."),))
    game = GameRecord("sample", root, headers={"White": "Learner"})
    assert game.root.main_line.uci == "e2e4"
    try:
        game.headers["Black"] = "Teacher"
    except TypeError:
        pass
    else:
        raise AssertionError("game headers must be immutable")

    step = LessonStep(
        "first-move", (), ChessAdapter.fen(ChessAdapter.initial_board()),
        "Choose a central pawn move.")
    lesson = Lesson(
        "opening-basics", 1, "Opening basics", "beginner", 5,
        "Develop pieces and control the centre.", "sample", (step,))
    assert lesson.steps[0].step_id == "first-move"


def test_board_view_renders_a_supplied_position_without_game_ui():
    pygame.init()
    surface = pygame.Surface((320, 320))
    piece_font = pygame.font.SysFont("dejavusans", 34)
    label_font = pygame.font.SysFont("monospace", 16, bold=True)
    view = BoardView(surface, 0, 0, 40, piece_font, label_font,
                     use_glyphs=False)
    board = ChessAdapter.from_fen(
        "8/8/8/3k4/8/4K3/8/7R w - - 0 1")
    view.draw_base()
    before = surface.copy()
    view.draw_position(
        board, white_color=(245, 245, 245), black_color=(32, 32, 32))
    assert pygame.image.tobytes(surface, "RGB") != pygame.image.tobytes(before, "RGB")
    assert view.pixel_to_square(view.square_to_pixel((3, 3))) == (3, 3)

    view.flipped = True
    assert view.pixel_to_square(view.square_to_pixel((3, 3))) == (3, 3)
    pygame.quit()


def main():
    for name, function in sorted(globals().items()):
        if name.startswith("test_") and callable(function):
            function()
            print("ok ", name)
    print("\nall milestone 0 foundation tests passed")


if __name__ == "__main__":
    main()
