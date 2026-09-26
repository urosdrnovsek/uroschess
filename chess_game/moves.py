"""Move generation, attack detection, and game-end detection."""

from .board import Move
from .pieces import WHITE, BLACK

# White pawns move "up" the screen: toward row 0. Black pawns move toward row 7.
PAWN_DIR = {WHITE: -1, BLACK: 1}
PROMO_ROW = {WHITE: 0, BLACK: 7}
START_ROW = {WHITE: 6, BLACK: 1}

KNIGHT_STEPS = [(-2, -1), (-2, 1), (-1, -2), (-1, 2), (1, -2), (1, 2), (2, -1), (2, 1)]
KING_STEPS = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
BISHOP_DIRS = [(-1, -1), (-1, 1), (1, -1), (1, 1)]
ROOK_DIRS = [(-1, 0), (1, 0), (0, -1), (0, 1)]


def on_board(r, c):
    return 0 <= r < 8 and 0 <= c < 8


def is_square_attacked(board, sq, by_color):
    """Is `sq` attacked by any piece of `by_color`?"""
    r, c = sq
    grid = board.grid

    # pawns: a `by_color` pawn attacks diagonally in its moving direction
    pd = PAWN_DIR[by_color]
    for dc in (-1, 1):
        pr, pc = r - pd, c - dc  # square a pawn would sit on to attack (r,c)
        if on_board(pr, pc) and grid[pr][pc] == by_color + "p":
            return True

    for dr, dc in KNIGHT_STEPS:
        nr, nc = r + dr, c + dc
        if on_board(nr, nc) and grid[nr][nc] == by_color + "n":
            return True

    for dr, dc in KING_STEPS:
        nr, nc = r + dr, c + dc
        if on_board(nr, nc) and grid[nr][nc] == by_color + "k":
            return True

    for dirs, types in ((BISHOP_DIRS, ("b", "q")), (ROOK_DIRS, ("r", "q"))):
        for dr, dc in dirs:
            nr, nc = r + dr, c + dc
            while on_board(nr, nc):
                p = grid[nr][nc]
                if p:
                    if p[0] == by_color and p[1] in types:
                        return True
                    break
                nr += dr
                nc += dc
    return False


def in_check(board, color):
    ks = board.king_square(color)
    if ks is None:
        return False
    return is_square_attacked(board, ks, BLACK if color == WHITE else WHITE)


def _pseudo_legal(board):
    """All moves for the side to move, ignoring whether the king is left in check."""
    moves = []
    color = board.side_to_move
    enemy = BLACK if color == WHITE else WHITE
    grid = board.grid

    for r in range(8):
        for c in range(8):
            p = grid[r][c]
            if not p or p[0] != color:
                continue
            t = p[1]

            if t == "p":
                _pawn_moves(board, r, c, color, enemy, moves)
            elif t == "n":
                for dr, dc in KNIGHT_STEPS:
                    nr, nc = r + dr, c + dc
                    if on_board(nr, nc) and (not grid[nr][nc] or grid[nr][nc][0] == enemy):
                        moves.append(Move((r, c), (nr, nc)))
            elif t == "k":
                for dr, dc in KING_STEPS:
                    nr, nc = r + dr, c + dc
                    if on_board(nr, nc) and (not grid[nr][nc] or grid[nr][nc][0] == enemy):
                        moves.append(Move((r, c), (nr, nc)))
                _castle_moves(board, r, c, color, enemy, moves)
            else:
                dirs = []
                if t in ("b", "q"):
                    dirs += BISHOP_DIRS
                if t in ("r", "q"):
                    dirs += ROOK_DIRS
                for dr, dc in dirs:
                    nr, nc = r + dr, c + dc
                    while on_board(nr, nc):
                        q = grid[nr][nc]
                        if not q:
                            moves.append(Move((r, c), (nr, nc)))
                        else:
                            if q[0] == enemy:
                                moves.append(Move((r, c), (nr, nc)))
                            break
                        nr += dr
                        nc += dc
    return moves


def _pawn_moves(board, r, c, color, enemy, moves):
    grid = board.grid
    d = PAWN_DIR[color]
    promo_row = PROMO_ROW[color]

    def add(frm, to, **kw):
        if to[0] == promo_row:
            for pr in ("q", "r", "b", "n"):
                moves.append(Move(frm, to, promo=pr, **kw))
        else:
            moves.append(Move(frm, to, **kw))

    # forward one
    nr = r + d
    if on_board(nr, c) and not grid[nr][c]:
        add((r, c), (nr, c))
        # forward two from start
        if r == START_ROW[color] and not grid[r + 2 * d][c]:
            moves.append(Move((r, c), (r + 2 * d, c)))
    # captures
    for dc in (-1, 1):
        nc = c + dc
        if not on_board(nr, nc):
            continue
        target = grid[nr][nc]
        if target and target[0] == enemy:
            add((r, c), (nr, nc))
        elif board.ep_target == (nr, nc):
            moves.append(Move((r, c), (nr, nc), is_en_passant=True))


def _castle_moves(board, r, c, color, enemy, moves):
    if in_check(board, color):
        return
    back_row = 7 if color == WHITE else 0
    if r != back_row or c != 4:
        return
    grid = board.grid
    # king side: squares f,g empty; e,f,g not attacked; rook on h
    if board.castling.get((color, "k")):
        if not grid[back_row][5] and not grid[back_row][6] and grid[back_row][7] == color + "r":
            if not is_square_attacked(board, (back_row, 5), enemy) and \
               not is_square_attacked(board, (back_row, 6), enemy):
                moves.append(Move((r, c), (back_row, 6), is_castle=True))
    # queen side: squares b,c,d empty; e,d,c not attacked; rook on a
    if board.castling.get((color, "q")):
        if not grid[back_row][1] and not grid[back_row][2] and not grid[back_row][3] \
           and grid[back_row][0] == color + "r":
            if not is_square_attacked(board, (back_row, 3), enemy) and \
               not is_square_attacked(board, (back_row, 2), enemy):
                moves.append(Move((r, c), (back_row, 2), is_castle=True))


def legal_moves(board):
    color = board.side_to_move
    result = []
    for m in _pseudo_legal(board):
        undo = board.make_move(m)
        if not in_check(board, color):
            result.append(m)
        board.undo_move(undo)
    return result


def insufficient_material(board):
    """True for K vs K, K+minor vs K, and K+B vs K+B with bishops of one color."""
    knights = bishops = 0
    bishop_colors = set()
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
                bishop_colors.add((r + c) % 2)
    if knights == 0 and bishops == 0:
        return True
    if knights + bishops == 1:
        return True
    if knights == 0 and len(bishop_colors) == 1:
        return True
    return False


def game_status(board):
    """Return 'ongoing', 'checkmate', 'stalemate', 'draw-fifty',
    'draw-repetition', or 'draw-material'."""
    if not legal_moves(board):
        return "checkmate" if in_check(board, board.side_to_move) else "stalemate"
    if board.repetition_count() >= 3:
        return "draw-repetition"
    if board.halfmove_clock >= 100:
        return "draw-fifty"
    if insufficient_material(board):
        return "draw-material"
    return "ongoing"
