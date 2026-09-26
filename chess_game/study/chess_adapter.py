"""Stable study-facing adapter around the existing chess implementation."""

from ..board import Board, Move
from ..moves import legal_moves
from ..notation import from_fen, san_to_move, to_fen, to_san


class MoveResolutionError(ValueError):
    """A move string could not be resolved in the supplied position."""


class ChessAdapter:
    """Create positions and apply UCI moves without exposing parser internals."""

    @staticmethod
    def initial_board():
        return Board()

    @staticmethod
    def from_fen(fen):
        return from_fen(fen)

    @staticmethod
    def fen(board):
        return to_fen(board)

    @staticmethod
    def legal_moves(board):
        return tuple(legal_moves(board))

    @classmethod
    def resolve_uci(cls, board, uci):
        matches = [move for move in cls.legal_moves(board) if str(move) == uci]
        if len(matches) != 1:
            raise MoveResolutionError(
                "move {!r} is not legal in position {}".format(uci, cls.fen(board)))
        return matches[0]

    @classmethod
    def apply_uci(cls, board, uci):
        move = cls.resolve_uci(board, uci)
        san = to_san(board, move)
        board.make_move(move)
        return move, san

    @classmethod
    def resolve_san(cls, board, san):
        try:
            return san_to_move(board, san)
        except ValueError as error:
            raise MoveResolutionError(
                "move {!r} is not legal in position {}".format(
                    san, cls.fen(board))) from error

    @classmethod
    def apply_san(cls, board, san):
        move = cls.resolve_san(board, san)
        canonical_san = to_san(board, move)
        board.make_move(move)
        return move, canonical_san

    @classmethod
    def replay(cls, moves, starting_fen=None):
        board = cls.from_fen(starting_fen) if starting_fen else cls.initial_board()
        sans = []
        resolved = []
        for uci in moves:
            move, san = cls.apply_uci(board, uci)
            resolved.append(move)
            sans.append(san)
        return board, tuple(resolved), tuple(sans)
