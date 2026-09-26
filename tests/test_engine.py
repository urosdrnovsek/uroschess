"""Engine / rules / notation checks. Run: python -m tests.test_engine"""

import random

from chess_game.board import Board
from chess_game.moves import legal_moves, game_status, insufficient_material
from chess_game import ai, zobrist
from chess_game import notation as N


def _mv(b, s):
    frm = (8 - int(s[1]), "abcdefgh".index(s[0]))
    to = (8 - int(s[3]), "abcdefgh".index(s[2]))
    return next(x for x in legal_moves(b) if x.frm == frm and x.to == to
               and (not x.promo or x.promo == s[4:5] or s[4:5] == ""))


def test_zobrist_incremental():
    b = Board()
    random.seed(7)

    def walk(depth):
        assert b.zobrist == zobrist.full_hash(b)
        if depth == 0:
            return
        for m in random.sample(legal_moves(b), k=min(6, len(legal_moves(b)))):
            u = b.make_move(m)
            walk(depth - 1)
            b.undo_move(u)
    walk(4)
    print("ok  zobrist incremental == full_hash")


def test_threefold():
    b = Board()
    for s in ["g1f3", "g8f6", "f3g1", "f6g8"] * 2 + ["g1f3", "g8f6"]:
        b.make_move(_mv(b, s))
    assert game_status(b) == "draw-repetition", game_status(b)
    print("ok  threefold repetition detected")


def test_insufficient_material():
    b = N.from_fen("8/8/8/4k3/8/8/8/4K3 w - - 0 1")
    assert insufficient_material(b) and game_status(b) == "draw-material"
    b = N.from_fen("8/8/8/4k3/8/5B2/8/4K3 w - - 0 1")
    assert insufficient_material(b)
    b = N.from_fen("8/8/8/4k3/8/5R2/8/4K3 w - - 0 1")
    assert not insufficient_material(b)
    print("ok  insufficient material")


def test_ai_finds_mate_in_one():
    b = N.from_fen("6k1/5ppp/8/8/8/8/8/R5K1 w - - 0 1")  # Ra8#
    m = ai.best_move(b, time_limit=1.0)
    assert N.to_san(b, m) == "Ra8#", N.to_san(b, m)
    print("ok  AI finds mate in one")


def test_ai_no_hanging_capture():
    # White queen on d1, Black pawn d7->d5 offered; a naive depth search that
    # stops mid-capture-sequence might grab it. Quiescence should see it's bad.
    b = N.from_fen("rnbqkbnr/ppp1pppp/8/3p4/8/8/PPPPQPPP/RNB1KBNR w KQkq - 0 1")
    m = ai.best_move(b, time_limit=1.5)
    assert not (m.to == (3, 3)), "AI grabbed the poisoned pawn with the queen"
    print("ok  AI declines a losing capture")


def test_san_pgn_roundtrip():
    b = Board()
    moves = []
    for s in ["e2e4", "c7c5", "g1f3", "d7d6", "d2d4", "c5d4", "f3d4", "g8f6",
              "b1c3", "a7a6", "f1e2", "e7e5", "d4b3", "f8e7", "e1g1"]:
        m = _mv(b, s)
        moves.append(m)
        b.make_move(m)
    pgn = N.game_to_pgn(moves)
    back = N.pgn_to_moves(pgn)
    assert [str(x) for x in back] == [str(x) for x in moves]
    b2 = N.from_fen(N.to_fen(b))
    assert N.to_fen(b2) == N.to_fen(b)
    print("ok  SAN/PGN/FEN roundtrip")


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    print("\nall engine tests passed")


if __name__ == "__main__":
    main()
