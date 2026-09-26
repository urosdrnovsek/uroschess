# Milestone 0: baseline and foundations

Completed on 22 September 2026.

## Delivered

- `run.sh` repairs an interrupted first-run installation by checking whether
  pygame can actually be imported before launching the application.
- Setup output remains visible and gives a retry instruction after failure.
- `BoardView` renders an arbitrary supplied board and owns board coordinate
  mapping, pieces, interaction overlays, and drag rendering. The existing play
  screen now uses it.
- UI-independent study models define the first contracts for annotated games
  and lessons.
- `ChessAdapter` provides one boundary around the existing rules, FEN, SAN,
  and UCI move resolution.
- Setuptools package discovery includes the new `chess_game` subpackages.
- `Instructions/`, local environments, generated renders, coverage output,
  and local `.env` files are excluded from version control.

## Architecture decision

The teaching core will remain MIT-compatible. The project will implement the
required annotated PGN support behind `chess_game.study.pgn_service` instead
of adding the GPL-3.0-or-later `python-chess` runtime dependency. See
[`0001-pgn-parser.md`](../architecture/0001-pgn-parser.md).

## Validation baseline

These commands passed after the changes:

```text
.venv/bin/python -m tests.test_foundations
.venv/bin/python -m tests.test_engine
.venv/bin/python -m tests.test_perft
.venv/bin/python -m scripts.smoke
.venv/bin/python -m compileall -q chess_game tests scripts
bash -n run.sh install.sh
git diff --check
```

The engine suite covered hashing, draw detection, SAN/PGN round trips, and
basic AI tactics. All reference perft positions passed through their configured
depths. The smoke check rendered the game in dummy SDL mode and completed an AI
move. The foundation suite rendered a supplied FEN through `BoardView` without
creating `ChessUI` or starting a game.

## Deferred to milestone 1

- Annotated PGN parsing and multiple-game import.
- Immutable replay navigation and variation selection.
- The game library and replay user interface.
- Broader lesson fields for questions, arrows, and exercise feedback.
