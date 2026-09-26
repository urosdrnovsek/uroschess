"""``python -m chess_game`` / the ``uroschess`` console script."""

from .ui import ChessUI


def main():
    ChessUI().run()


if __name__ == "__main__":
    main()
