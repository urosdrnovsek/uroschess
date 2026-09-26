"""Perft: count leaf nodes of the move tree to validate move generation.

Run: python -m tests.test_perft
"""

from chess_game.board import Board
from chess_game.moves import legal_moves
from chess_game.notation import from_fen


def perft(board, depth):
    if depth == 0:
        return 1
    total = 0
    for m in legal_moves(board):
        undo = board.make_move(m)
        total += perft(board, depth - 1)
        board.undo_move(undo)
    return total


# (name, fen or None for start position, [expected perft(1..n)])
CASES = [
    ("startpos", None, [20, 400, 8902, 197281]),
    ("kiwipete",
     "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1",
     [48, 2039, 97862]),
    ("position 3",
     "8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1",
     [14, 191, 2812, 43238]),
    ("position 4",
     "r3k2r/Pppp1ppp/1b3nbN/nP6/BBP1P3/q4N2/Pp1P2PP/R2Q1RK1 w kq - 0 1",
     [6, 264, 9467]),
    ("position 5",
     "rnbq1k1r/pp1Pbppp/2p5/8/2B5/8/PPP1NnPP/RNBQK2R w KQ - 1 8",
     [44, 1486, 62379]),
]


def test_perft_positions():
    for name, fen, expected in CASES:
        board = Board() if fen is None else from_fen(fen)
        for depth, exp in enumerate(expected, start=1):
            assert perft(board, depth) == exp, f"{name} perft({depth})"


def main():
    ok = True
    for name, fen, expected in CASES:
        board = Board() if fen is None else from_fen(fen)
        for depth, exp in enumerate(expected, start=1):
            got = perft(board, depth)
            status = "ok" if got == exp else "FAIL"
            if got != exp:
                ok = False
            print(f"{name:>12}  perft({depth}) = {got:>9}  expected {exp:>9}  [{status}]")
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
