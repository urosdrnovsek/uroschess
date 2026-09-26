"""SAN (Standard Algebraic Notation) and minimal PGN / FEN support."""

from .board import Board, Move
from .moves import legal_moves, in_check, game_status
from .pieces import WHITE, BLACK

_FILES = "abcdefgh"


def sq_name(sq):
    r, c = sq
    return f"{_FILES[c]}{8 - r}"


def parse_sq(name):
    return (8 - int(name[1]), _FILES.index(name[0]))


def to_san(board, move):
    """SAN for `move`, which must be legal in `board` (board is not mutated)."""
    piece = board.piece_at(move.frm)
    ptype = piece[1]
    victim = board.piece_at(move.to)
    is_capture = bool(victim) or move.is_en_passant

    if move.is_castle:
        san = "O-O" if move.to[1] == 6 else "O-O-O"
    elif ptype == "p":
        san = ""
        if is_capture:
            san += _FILES[move.frm[1]] + "x"
        san += sq_name(move.to)
        if move.promo:
            san += "=" + move.promo.upper()
    else:
        san = ptype.upper()
        # disambiguation: other same-type pieces that can also reach move.to
        others = [
            m for m in legal_moves(board)
            if m.to == move.to and m.frm != move.frm
            and board.piece_at(m.frm) and board.piece_at(m.frm)[1] == ptype
        ]
        if others:
            same_file = any(m.frm[1] == move.frm[1] for m in others)
            same_rank = any(m.frm[0] == move.frm[0] for m in others)
            if not same_file:
                san += _FILES[move.frm[1]]
            elif not same_rank:
                san += str(8 - move.frm[0])
            else:
                san += sq_name(move.frm)
        if is_capture:
            san += "x"
        san += sq_name(move.to)

    undo = board.make_move(move)
    if not legal_moves(board):
        san += "#" if in_check(board, board.side_to_move) else ""
    elif in_check(board, board.side_to_move):
        san += "+"
    board.undo_move(undo)
    return san


def to_fen(board):
    rows = []
    for r in range(8):
        empty = 0
        out = ""
        for c in range(8):
            p = board.grid[r][c]
            if not p:
                empty += 1
                continue
            if empty:
                out += str(empty)
                empty = 0
            out += p[1].upper() if p[0] == WHITE else p[1]
        if empty:
            out += str(empty)
        rows.append(out)
    placement = "/".join(rows)
    side = "w" if board.side_to_move == WHITE else "b"
    rights = ""
    for color, sym in ((WHITE, "KQ"), (BLACK, "kq")):
        if board.castling.get((color, "k")):
            rights += sym[0]
        if board.castling.get((color, "q")):
            rights += sym[1]
    rights = rights or "-"
    ep = sq_name(board.ep_target) if board.ep_target else "-"
    return f"{placement} {side} {rights} {ep} {board.halfmove_clock} {board.fullmove_number}"


def from_fen(fen):
    placement, side, rights, ep, half, full = fen.split()
    board = Board.__new__(Board)
    board.grid = [["" for _ in range(8)] for _ in range(8)]
    for r, row in enumerate(placement.split("/")):
        c = 0
        for ch in row:
            if ch.isdigit():
                c += int(ch)
            else:
                color = WHITE if ch.isupper() else BLACK
                board.grid[r][c] = color + ch.lower()
                c += 1
    board.side_to_move = WHITE if side == "w" else BLACK
    board.castling = {
        (WHITE, "k"): "K" in rights, (WHITE, "q"): "Q" in rights,
        (BLACK, "k"): "k" in rights, (BLACK, "q"): "q" in rights,
    }
    board.ep_target = None if ep == "-" else parse_sq(ep)
    board.halfmove_clock = int(half)
    board.fullmove_number = int(full)
    from . import zobrist
    board.zobrist = zobrist.full_hash(board)
    board.history = [board.zobrist]
    return board


def game_to_pgn(moves, board_start=None, result="*", headers=None):
    """`moves` is a list of Move objects played from the start position."""
    b = board_start.clone() if board_start else Board()
    hdr = {
        "Event": "Casual game", "Site": "chess_game", "Round": "-",
        "White": "White", "Black": "Black", "Result": result,
    }
    if headers:
        hdr.update(headers)
    lines = [f'[{k} "{v}"]' for k, v in hdr.items()]
    body = []
    for i, m in enumerate(moves):
        san = to_san(b, m)
        if i % 2 == 0:
            body.append(f"{b.fullmove_number}. {san}")
        else:
            body.append(san)
        b.make_move(m)
    body.append(result)
    return "\n".join(lines) + "\n\n" + " ".join(body) + "\n"


def san_to_move(board, san):
    """Resolve standard algebraic notation to one legal move."""
    san = san.strip().replace("0-0-0", "O-O-O").replace("0-0", "O-O")
    san = san.rstrip("+#!?")
    for m in legal_moves(board):
        if to_san(board, m).rstrip("+#!?") == san:
            return m
    raise ValueError(f"illegal/ambiguous SAN: {san}")


def pgn_to_moves(text):
    """Parse the movetext of a PGN (headers optional). Returns list[Move]."""
    lines = [ln for ln in text.splitlines() if not ln.startswith("[")]
    movetext = " ".join(lines)
    for tok in ("1-0", "0-1", "1/2-1/2", "*"):
        movetext = movetext.replace(tok, " ")
    # strip move numbers and comments
    import re
    movetext = re.sub(r"\{[^}]*\}", " ", movetext)
    movetext = re.sub(r"\d+\.(\.\.)?", " ", movetext)
    board = Board()
    moves = []
    for tok in movetext.split():
        tok = tok.strip()
        if not tok:
            continue
        m = san_to_move(board, tok)
        board.make_move(m)
        moves.append(m)
    return moves
