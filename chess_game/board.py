"""Board state and move application.

Coordinates: (row, col) with row 0 = rank 8 (top of the screen), row 7 = rank 1.
White's back rank is row 7, Black's back rank is row 0.
"""

from dataclasses import dataclass, field

from . import pieces
from . import zobrist
from .pieces import WHITE, BLACK


@dataclass(frozen=True)
class Move:
    frm: tuple            # (row, col)
    to: tuple             # (row, col)
    promo: str = None     # piece type to promote to, e.g. 'q'
    is_castle: bool = False
    is_en_passant: bool = False

    def __str__(self):
        files = "abcdefgh"
        fr = f"{files[self.frm[1]]}{8 - self.frm[0]}"
        to = f"{files[self.to[1]]}{8 - self.to[0]}"
        return fr + to + (self.promo or "")


@dataclass
class _Undo:
    move: Move
    captured: str
    prev_castling: dict
    prev_ep: tuple
    prev_side: str
    prev_halfmove: int
    prev_zobrist: int = 0
    rook_from: tuple = None
    rook_to: tuple = None


def initial_grid():
    back = ["r", "n", "b", "q", "k", "b", "n", "r"]
    grid = [["" for _ in range(8)] for _ in range(8)]
    for c in range(8):
        grid[0][c] = "b" + back[c]
        grid[1][c] = "bp"
        grid[6][c] = "wp"
        grid[7][c] = "w" + back[c]
    return grid


class Board:
    def __init__(self):
        self.grid = initial_grid()
        self.side_to_move = WHITE
        # castling rights: can this (color, side) still castle?
        self.castling = {
            (WHITE, "k"): True, (WHITE, "q"): True,
            (BLACK, "k"): True, (BLACK, "q"): True,
        }
        self.ep_target = None       # square that can be captured en passant
        self.halfmove_clock = 0     # plies since last capture/pawn move
        self.fullmove_number = 1    # incremented after every Black move
        self.zobrist = zobrist.full_hash(self)
        # Zobrist keys of every position that has occurred, this one included.
        # Used for threefold-repetition detection.
        self.history = [self.zobrist]

    # -- helpers -----------------------------------------------------------
    def piece_at(self, sq):
        return self.grid[sq[0]][sq[1]]

    def king_square(self, color):
        target = color + "k"
        for r in range(8):
            for c in range(8):
                if self.grid[r][c] == target:
                    return (r, c)
        return None

    def clone(self):
        b = Board.__new__(Board)
        b.grid = [row[:] for row in self.grid]
        b.side_to_move = self.side_to_move
        b.castling = dict(self.castling)
        b.ep_target = self.ep_target
        b.halfmove_clock = self.halfmove_clock
        b.fullmove_number = self.fullmove_number
        b.zobrist = self.zobrist
        b.history = self.history[:]
        return b

    def repetition_count(self):
        """How many times the current position has appeared (>=3 is a draw)."""
        return self.history.count(self.zobrist)

    # -- move application ------------------------------------------------
    def make_move(self, move):
        r0, c0 = move.frm
        r1, c1 = move.to
        piece = self.grid[r0][c0]
        color = piece[0]
        ptype = piece[1]

        undo = _Undo(
            move=move,
            captured="",
            prev_castling=dict(self.castling),
            prev_ep=self.ep_target,
            prev_side=self.side_to_move,
            prev_halfmove=self.halfmove_clock,
            prev_zobrist=self.zobrist,
        )
        h = self.zobrist
        K = zobrist.PIECE_KEYS

        # en passant capture: the taken pawn is not on the destination square
        if move.is_en_passant:
            cap_row = r0
            undo.captured = self.grid[cap_row][c1]
            self.grid[cap_row][c1] = ""
            h ^= K[undo.captured][cap_row][c1]
        else:
            undo.captured = self.grid[r1][c1]
            if undo.captured:
                h ^= K[undo.captured][r1][c1]

        # move the piece
        self.grid[r1][c1] = piece
        self.grid[r0][c0] = ""
        h ^= K[piece][r0][c0]

        # promotion
        if move.promo:
            self.grid[r1][c1] = color + move.promo
        h ^= K[self.grid[r1][c1]][r1][c1]

        # castling: move the rook too
        if move.is_castle:
            if c1 == 6:  # king side
                undo.rook_from, undo.rook_to = (r0, 7), (r0, 5)
            else:        # queen side
                undo.rook_from, undo.rook_to = (r0, 0), (r0, 3)
            rook = self.grid[undo.rook_from[0]][undo.rook_from[1]]
            self.grid[undo.rook_to[0]][undo.rook_to[1]] = rook
            self.grid[undo.rook_from[0]][undo.rook_from[1]] = ""
            h ^= K[rook][undo.rook_from[0]][undo.rook_from[1]]
            h ^= K[rook][undo.rook_to[0]][undo.rook_to[1]]

        # update castling rights
        if ptype == "k":
            self.castling[(color, "k")] = False
            self.castling[(color, "q")] = False
        if ptype == "r":
            if (r0, c0) == (7, 0) or (r0, c0) == (0, 0):
                self.castling[(color, "q")] = False
            if (r0, c0) == (7, 7) or (r0, c0) == (0, 7):
                self.castling[(color, "k")] = False
        # a rook getting captured also removes rights
        for (cr, cc), key in (
            ((7, 0), (WHITE, "q")), ((7, 7), (WHITE, "k")),
            ((0, 0), (BLACK, "q")), ((0, 7), (BLACK, "k")),
        ):
            if (r1, c1) == (cr, cc):
                self.castling[key] = False

        # fold any castling-rights changes into the hash
        for key, was_on in undo.prev_castling.items():
            if was_on != self.castling[key]:
                h ^= zobrist.CASTLE_KEYS[key]

        # en passant target for the *next* move
        if undo.prev_ep is not None:
            h ^= zobrist.EP_FILE_KEYS[undo.prev_ep[1]]
        if ptype == "p" and abs(r1 - r0) == 2:
            self.ep_target = ((r0 + r1) // 2, c0)
        else:
            self.ep_target = None
        if self.ep_target is not None:
            h ^= zobrist.EP_FILE_KEYS[self.ep_target[1]]

        # halfmove clock
        if ptype == "p" or undo.captured:
            self.halfmove_clock = 0
        else:
            self.halfmove_clock += 1

        if color == BLACK:
            self.fullmove_number += 1
        self.side_to_move = BLACK if color == WHITE else WHITE
        h ^= zobrist.SIDE_KEY

        self.zobrist = h
        self.history.append(h)
        return undo

    def undo_move(self, undo):
        move = undo.move
        r0, c0 = move.frm
        r1, c1 = move.to
        piece = self.grid[r1][c1]
        color = piece[0]

        # undo promotion
        if move.promo:
            piece = color + "p"

        self.grid[r0][c0] = piece
        self.grid[r1][c1] = ""

        if move.is_en_passant:
            self.grid[r1][c1] = ""
            self.grid[r0][c1] = undo.captured
        else:
            self.grid[r1][c1] = undo.captured

        if move.is_castle:
            self.grid[undo.rook_from[0]][undo.rook_from[1]] = self.grid[undo.rook_to[0]][undo.rook_to[1]]
            self.grid[undo.rook_to[0]][undo.rook_to[1]] = ""

        self.castling = dict(undo.prev_castling)
        self.ep_target = undo.prev_ep
        if undo.prev_side == BLACK:
            self.fullmove_number -= 1
        self.side_to_move = undo.prev_side
        self.halfmove_clock = undo.prev_halfmove
        self.zobrist = undo.prev_zobrist
        self.history.pop()
