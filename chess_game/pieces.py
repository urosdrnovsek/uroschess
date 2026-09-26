"""Piece constants, colors, and Unicode glyphs.

A piece is a two-character string: color ('w'/'b') + type ('p','n','b','r','q','k').
An empty square is the empty string "".
"""

WHITE = "w"
BLACK = "b"

PAWN = "p"
KNIGHT = "n"
BISHOP = "b"
ROOK = "r"
QUEEN = "q"
KING = "k"

PIECE_TYPES = (PAWN, KNIGHT, BISHOP, ROOK, QUEEN, KING)

# Centipawn values used by the evaluation.
VALUES = {
    PAWN: 100,
    KNIGHT: 320,
    BISHOP: 330,
    ROOK: 500,
    QUEEN: 900,
    KING: 20000,
}

# Unicode chess symbols. We render every piece with the *solid* glyphs and just
# tint them by color, which reads more clearly on a colored board than mixing
# outline and solid glyphs.
GLYPHS = {
    KING: "♚",
    QUEEN: "♛",
    ROOK: "♜",
    BISHOP: "♝",
    KNIGHT: "♞",
    PAWN: "♟",
}

# ASCII fallback if the chess glyphs render as tofu.
LETTERS = {
    KING: "K",
    QUEEN: "Q",
    ROOK: "R",
    BISHOP: "B",
    KNIGHT: "N",
    PAWN: "P",
}


def color_of(piece):
    return piece[0] if piece else None


def type_of(piece):
    return piece[1] if piece else None


def opponent(color):
    return BLACK if color == WHITE else WHITE
