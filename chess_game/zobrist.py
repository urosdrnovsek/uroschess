"""Zobrist hashing keys, shared by the board (incremental hash) and the AI's
transposition table.

The keys are generated from a fixed seed so a given position always hashes to
the same value across runs (handy for debugging and for a persistent opening
book, should we ever add one).
"""

import random

from .pieces import WHITE, BLACK, PIECE_TYPES

_rng = random.Random(0xC0FFEE)

# piece key for every (color+type, row, col)
PIECE_KEYS = {}
for _color in (WHITE, BLACK):
    for _t in PIECE_TYPES:
        PIECE_KEYS[_color + _t] = [
            [_rng.getrandbits(64) for _ in range(8)] for _ in range(8)
        ]

SIDE_KEY = _rng.getrandbits(64)  # XOR'd in when Black is to move

# castling rights, in a fixed order
CASTLE_KEYS = {
    (WHITE, "k"): _rng.getrandbits(64),
    (WHITE, "q"): _rng.getrandbits(64),
    (BLACK, "k"): _rng.getrandbits(64),
    (BLACK, "q"): _rng.getrandbits(64),
}

# en-passant file (only the file matters for repetition equivalence)
EP_FILE_KEYS = [_rng.getrandbits(64) for _ in range(8)]


def full_hash(board):
    """Compute a position's Zobrist key from scratch."""
    h = 0
    for r in range(8):
        for c in range(8):
            p = board.grid[r][c]
            if p:
                h ^= PIECE_KEYS[p][r][c]
    if board.side_to_move == BLACK:
        h ^= SIDE_KEY
    for key, on in board.castling.items():
        if on:
            h ^= CASTLE_KEYS[key]
    if board.ep_target is not None:
        h ^= EP_FILE_KEYS[board.ep_target[1]]
    return h
