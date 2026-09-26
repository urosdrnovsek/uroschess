"""Search: iterative-deepening negamax with alpha-beta, a transposition table,
quiescence search, and MVV-LVA / killer move ordering.

`best_move()` is the entry point. It searches until either `max_depth` or
`time_limit` (seconds) is hit, whichever comes first, and always returns a move
from the deepest *completed* iteration.
"""

import time

from .pieces import VALUES, WHITE, BLACK
from .moves import legal_moves, in_check

MATE = 1_000_000
MATE_THRESHOLD = MATE - 1000  # scores above this are "mate in N"

# Piece-square tables from White's perspective, row 0 = rank 8 (Black's side).
_PST = {
    "p": [
        [0, 0, 0, 0, 0, 0, 0, 0],
        [50, 50, 50, 50, 50, 50, 50, 50],
        [10, 10, 20, 30, 30, 20, 10, 10],
        [5, 5, 10, 25, 25, 10, 5, 5],
        [0, 0, 0, 20, 20, 0, 0, 0],
        [5, -5, -10, 0, 0, -10, -5, 5],
        [5, 10, 10, -20, -20, 10, 10, 5],
        [0, 0, 0, 0, 0, 0, 0, 0],
    ],
    "n": [
        [-50, -40, -30, -30, -30, -30, -40, -50],
        [-40, -20, 0, 0, 0, 0, -20, -40],
        [-30, 0, 10, 15, 15, 10, 0, -30],
        [-30, 5, 15, 20, 20, 15, 5, -30],
        [-30, 0, 15, 20, 20, 15, 0, -30],
        [-30, 5, 10, 15, 15, 10, 5, -30],
        [-40, -20, 0, 5, 5, 0, -20, -40],
        [-50, -40, -30, -30, -30, -30, -40, -50],
    ],
    "b": [
        [-20, -10, -10, -10, -10, -10, -10, -20],
        [-10, 0, 0, 0, 0, 0, 0, -10],
        [-10, 0, 5, 10, 10, 5, 0, -10],
        [-10, 5, 5, 10, 10, 5, 5, -10],
        [-10, 0, 10, 10, 10, 10, 0, -10],
        [-10, 10, 10, 10, 10, 10, 10, -10],
        [-10, 5, 0, 0, 0, 0, 5, -10],
        [-20, -10, -10, -10, -10, -10, -10, -20],
    ],
    "r": [
        [0, 0, 0, 0, 0, 0, 0, 0],
        [5, 10, 10, 10, 10, 10, 10, 5],
        [-5, 0, 0, 0, 0, 0, 0, -5],
        [-5, 0, 0, 0, 0, 0, 0, -5],
        [-5, 0, 0, 0, 0, 0, 0, -5],
        [-5, 0, 0, 0, 0, 0, 0, -5],
        [-5, 0, 0, 0, 0, 0, 0, -5],
        [0, 0, 0, 5, 5, 0, 0, 0],
    ],
    "q": [
        [-20, -10, -10, -5, -5, -10, -10, -20],
        [-10, 0, 0, 0, 0, 0, 0, -10],
        [-10, 0, 5, 5, 5, 5, 0, -10],
        [-5, 0, 5, 5, 5, 5, 0, -5],
        [0, 0, 5, 5, 5, 5, 0, -5],
        [-10, 5, 5, 5, 5, 5, 0, -10],
        [-10, 0, 5, 0, 0, 0, 0, -10],
        [-20, -10, -10, -5, -5, -10, -10, -20],
    ],
    "k": [
        [-30, -40, -40, -50, -50, -40, -40, -30],
        [-30, -40, -40, -50, -50, -40, -40, -30],
        [-30, -40, -40, -50, -50, -40, -40, -30],
        [-30, -40, -40, -50, -50, -40, -40, -30],
        [-20, -30, -30, -40, -40, -30, -30, -20],
        [-10, -20, -20, -20, -20, -20, -20, -10],
        [20, 20, 0, 0, 0, 0, 20, 20],
        [20, 30, 10, 0, 0, 10, 30, 20],
    ],
}

# King wants the centre once the queens and rooks are gone.
_PST_K_END = [
    [-50, -40, -30, -20, -20, -30, -40, -50],
    [-30, -20, -10, 0, 0, -10, -20, -30],
    [-30, -10, 20, 30, 30, 20, -10, -30],
    [-30, -10, 30, 40, 40, 30, -10, -30],
    [-30, -10, 30, 40, 40, 30, -10, -30],
    [-30, -10, 20, 30, 30, 20, -10, -30],
    [-30, -30, 0, 0, 0, 0, -30, -30],
    [-50, -30, -30, -30, -30, -30, -30, -50],
]

# Non-pawn, non-king material (both sides) at the start, for the endgame blend.
_PHASE_MAX = 2 * (VALUES["n"] * 2 + VALUES["b"] * 2 + VALUES["r"] * 2 + VALUES["q"])


def evaluate(board):
    """Static score from White's perspective (positive = White is better)."""
    score = 0
    non_pawn = 0
    king_sq = {}
    for r in range(8):
        row = board.grid[r]
        for c in range(8):
            p = row[c]
            if not p:
                continue
            color, t = p[0], p[1]
            if t == "k":
                king_sq[color] = (r, c)
                continue
            if t != "p":
                non_pawn += VALUES[t]
            pr = r if color == WHITE else 7 - r
            val = VALUES[t] + _PST[t][pr][c]
            score += val if color == WHITE else -val

    # tapered king evaluation
    phase = min(non_pawn, _PHASE_MAX) / _PHASE_MAX  # 1.0 opening -> 0.0 endgame
    for color, (r, c) in king_sq.items():
        pr = r if color == WHITE else 7 - r
        mg = _PST["k"][pr][c]
        eg = _PST_K_END[pr][c]
        val = VALUES["k"] + mg * phase + eg * (1 - phase)
        score += val if color == WHITE else -val

    return int(score)


class _Timeout(Exception):
    pass


class Engine:
    """One search. Holds the transposition table and killer tables for a run."""

    def __init__(self, time_limit=2.0, max_depth=64):
        self.time_limit = time_limit
        self.max_depth = max_depth
        self.tt = {}                     # zobrist -> (depth, flag, value, move)
        self.killers = [[None, None] for _ in range(max_depth + 1)]
        self.nodes = 0
        self.deadline = None

    # -- helpers -------------------------------------------------------------
    def _draw(self, board):
        return (board.halfmove_clock >= 100
                or board.repetition_count() >= 2
                or _insufficient(board))

    def _order(self, board, moves, tt_move, ply):
        k1, k2 = self.killers[ply] if ply < len(self.killers) else (None, None)

        def key(m):
            if m == tt_move:
                return 1_000_000
            victim = board.piece_at(m.to)
            if victim:
                return 100_000 + VALUES[victim[1]] * 10 - VALUES[board.piece_at(m.frm)[1]]
            if m.promo:
                return 90_000 + VALUES[m.promo]
            if m == k1:
                return 80_001
            if m == k2:
                return 80_000
            return 0

        moves.sort(key=key, reverse=True)

    # -- quiescence -------------------------------------------------------
    def _qsearch(self, board, alpha, beta):
        self.nodes += 1
        if self.nodes % 2048 == 0 and time.monotonic() > self.deadline:
            raise _Timeout

        stand = evaluate(board) if board.side_to_move == WHITE else -evaluate(board)
        if stand >= beta:
            return beta
        if stand > alpha:
            alpha = stand

        moves = [m for m in legal_moves(board) if board.piece_at(m.to) or m.promo]
        moves.sort(
            key=lambda m: (VALUES[board.piece_at(m.to)[1]] if board.piece_at(m.to) else 0)
            + (VALUES[m.promo] if m.promo else 0),
            reverse=True,
        )
        for m in moves:
            undo = board.make_move(m)
            score = -self._qsearch(board, -beta, -alpha)
            board.undo_move(undo)
            if score >= beta:
                return beta
            if score > alpha:
                alpha = score
        return alpha

    # -- main search -----------------------------------------------------
    def _search(self, board, depth, alpha, beta, ply):
        self.nodes += 1
        if self.nodes % 2048 == 0 and time.monotonic() > self.deadline:
            raise _Timeout

        if ply > 0 and self._draw(board):
            return 0

        alpha_orig = beta_orig = None
        tt_move = None
        entry = self.tt.get(board.zobrist)
        if entry and entry[0] >= depth and ply > 0:
            e_depth, flag, value, move = entry
            if flag == "EXACT":
                return value
            if flag == "LOWER" and value > alpha:
                alpha = value
            elif flag == "UPPER" and value < beta:
                beta = value
            if alpha >= beta:
                return value
        if entry:
            tt_move = entry[3]

        alpha_orig = alpha

        moves = legal_moves(board)
        if not moves:
            if in_check(board, board.side_to_move):
                return -MATE + ply       # closer mates score higher (less negative)
            return 0

        if depth <= 0:
            return self._qsearch(board, alpha, beta)

        self._order(board, moves, tt_move, ply)

        best = -MATE * 2
        best_move = moves[0]
        for m in moves:
            undo = board.make_move(m)
            score = -self._search(board, depth - 1, -beta, -alpha, ply + 1)
            board.undo_move(undo)
            if score > best:
                best = score
                best_move = m
            if best > alpha:
                alpha = best
            if alpha >= beta:
                if not board.piece_at(m.to) and not m.promo and ply < len(self.killers):
                    ks = self.killers[ply]
                    if m != ks[0]:
                        ks[1] = ks[0]
                        ks[0] = m
                break

        flag = "EXACT"
        if best <= alpha_orig:
            flag = "UPPER"
        elif best >= beta:
            flag = "LOWER"
        # Don't cache mate scores: their value is ply-relative and would be
        # wrong if the same position is reached at a different distance.
        if abs(best) < MATE_THRESHOLD:
            self.tt[board.zobrist] = (depth, flag, best, best_move)
        return best

    # -- driver --------------------------------------------------------
    def search(self, board, on_progress=None):
        self.deadline = time.monotonic() + self.time_limit
        root_moves = legal_moves(board)
        if not root_moves:
            return None, 0, []
        best_move = root_moves[0]
        best_score = 0
        pv = [best_move]

        for depth in range(1, self.max_depth + 1):
            try:
                score, move, line = self._root(board, depth)
            except _Timeout:
                break
            best_move, best_score, pv = move, score, line
            if on_progress:
                on_progress(depth, best_score, pv, self.nodes)
            if abs(best_score) > MATE_THRESHOLD:
                break  # forced mate found, no point searching deeper
        return best_move, best_score, pv

    def _root(self, board, depth):
        moves = legal_moves(board)
        entry = self.tt.get(board.zobrist)
        self._order(board, moves, entry[3] if entry else None, 0)

        alpha, beta = -MATE * 2, MATE * 2
        best = -MATE * 2
        best_move = moves[0]
        for m in moves:
            undo = board.make_move(m)
            score = -self._search(board, depth - 1, -beta, -alpha, 1)
            board.undo_move(undo)
            if score > best:
                best = score
                best_move = m
                if best > alpha:
                    alpha = best
        self.tt[board.zobrist] = (depth, "EXACT", best, best_move)
        return best, best_move, self._extract_pv(board, best_move, depth)

    def _extract_pv(self, board, first, depth):
        pv = []
        undos = []
        m = first
        for _ in range(depth):
            if m is None:
                break
            legal = legal_moves(board)
            if m not in legal:
                break
            pv.append(m)
            undos.append(board.make_move(m))
            entry = self.tt.get(board.zobrist)
            m = entry[3] if entry else None
        for u in reversed(undos):
            board.undo_move(u)
        return pv


def _insufficient(board):
    knights = bishops = 0
    colors = set()
    for r in range(8):
        for c in range(8):
            p = board.grid[r][c]
            if not p:
                continue
            t = p[1]
            if t in ("p", "r", "q"):
                return False
            if t == "n":
                knights += 1
            elif t == "b":
                bishops += 1
                colors.add((r + c) % 2)
    if knights + bishops <= 1:
        return True
    return knights == 0 and len(colors) == 1


def best_move(board, depth=None, time_limit=2.0, on_progress=None):
    """Best move for the side to move, or None if the game is over.

    `depth` caps the iterative deepening (None = only the time limit bounds it).
    """
    eng = Engine(time_limit=time_limit, max_depth=depth or 64)
    move, _score, _pv = eng.search(board, on_progress=on_progress)
    return move


def analyse(board, time_limit=2.0, max_depth=64, on_progress=None):
    """Like best_move but returns (move, score, pv, nodes)."""
    eng = Engine(time_limit=time_limit, max_depth=max_depth)
    move, score, pv = eng.search(board, on_progress=on_progress)
    return move, score, pv, eng.nodes
