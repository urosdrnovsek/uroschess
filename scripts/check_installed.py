"""Exercise an installed wheel outside the checkout, without network access.

Run this script by absolute path from a temporary directory in the wheel's
virtual environment. It deliberately never adds the repository to sys.path.
"""
import os
from pathlib import Path
from importlib import resources
import tempfile

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')

import pygame
import chess_game
from chess_game.study import load_game_library, resolve_lesson
from chess_game.ui import ChessUI
from chess_game.challenge import ROSTER


def main():
    checkout = Path(__file__).resolve().parents[1]
    package = Path(chess_game.__file__).resolve()
    if checkout in package.parents:
        raise RuntimeError('This check loaded the checkout instead of the installed wheel.')
    library = load_game_library()
    assert not library.errors, library.errors
    for entry in library.lesson_entries:
        resolve_lesson(entry.game, entry.lesson)
    with tempfile.TemporaryDirectory() as directory:
        ui = ChessUI(Path(directory) / 'progress.sqlite3')
        try:
            for size in ((980, 760), (420, 720), (360, 320)):
                ui._on_resize(*size)
                ui._to_menu()
                ui._build_menu_buttons()
                ui._draw()
            ui._on_resize(980, 760)
            ui._start_challenge('w', 'chicky')
            match_id = ui.challenge.match_id
            ui._open_challenge_from_game()
            ui._resume_challenge()
            assert ui.challenge.match_id == match_id
            ui._to_menu()
            ui.start_lesson(library.lesson_entry('chicky-knight-transfer'))
            ui._build_lesson_buttons()
            ui._draw()
            ui.start_replay(library.entries[0])
            ui._build_replay_buttons()
            ui._draw()
            for opponent in ROSTER:
                assert ui.game_library.player(opponent.ident)
                resource = resources.files('chess_game.assets.portraits').joinpath(
                    opponent.portrait)
                with resources.as_file(resource) as portrait_path:
                    portrait = pygame.image.load(str(portrait_path))
                    assert portrait.get_width() > 0 and portrait.get_height() > 0
        finally:
            ui._cancel_challenge_search()
            ui.progress_store.close()
            pygame.quit()
    print('Installed wheel: content, menus, lesson, replay and challenge resume passed.')


if __name__ == '__main__':
    main()
