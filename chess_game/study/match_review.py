"""Small match reviews based on replayed rules, without engine evaluations."""

from dataclasses import dataclass

from ..board import Board
from ..moves import game_status, in_check, legal_moves
from ..notation import to_fen, to_san
from .models import GameRecord, MoveNode
from .content import LibraryEntry


@dataclass(frozen=True)
class ReviewMoment:
    ply: int
    explanation: str
    practice_id: str


@dataclass(frozen=True)
class MatchReview:
    entry: LibraryEntry
    moments: tuple
    practice_id: str


def review_match(session):
    """Verify the complete history before producing at most two factual notes."""
    if session.status == 'ongoing':
        raise ValueError('Finish the match before reviewing it.')
    board = Board()
    moments = []
    for ply, move in enumerate(session.moves, 1):
        if game_status(board) != 'ongoing' or move not in legal_moves(board):
            raise ValueError('The match history cannot be verified.')
        human_turn = board.side_to_move == session.color
        checked = in_check(board, board.side_to_move)
        san = to_san(board, move)
        board.make_move(move)
        status = game_status(board)
        if human_turn and checked:
            moments.append(ReviewMoment(ply,
                'You answered check with {}. Your king is no longer in check. '
                'When checked, look for a king move, a capture, or a block.'.format(san),
                'chicky-king-safety'))
        elif human_turn and move.is_castle:
            moments.append(ReviewMoment(ply,
                'You castled with {}: your king and rook moved together. '
                'Castling can help bring a rook into play and shelter the king.'.format(san),
                'olive-catalan-king-safety'))
        elif human_turn and move.promo:
            moments.append(ReviewMoment(ply,
                'Your pawn reached the last rank with {} and became a new piece.'.format(san),
                'tina-first-promotion'))
        if status == 'checkmate':
            actor = 'You' if human_turn else session.opponent.name
            moments.append(ReviewMoment(ply,
                '{} delivered checkmate with {}. The king is in check, and there '
                'is no legal move to escape it.'.format(actor, san),
                'chicky-simple-mate' if human_turn else 'chicky-king-safety'))
        elif status == 'stalemate':
            moments.append(ReviewMoment(ply,
                '{} left the next player with no legal move and no check: '
                'stalemate is a draw.'.format(san), 'mate-or-stalemate'))
    if to_fen(board) != to_fen(session.board):
        raise ValueError('The match position does not match its history.')
    actual = game_status(board)
    if session.status != 'resignation' and session.status != actual:
        raise ValueError('The match result does not match its history.')
    # Keep one earlier learning moment and the final observed moment.
    # One board position is one moment, even if it both evades check and mates.
    moments = list({moment.ply: moment for moment in moments}.values())
    selected = tuple(moments if len(moments) <= 2 else (moments[0], moments[-1]))
    comments = {moment.ply: moment.explanation for moment in selected}
    summary = 'Review your match with {}. '.format(session.opponent.name)
    if selected:
        summary += 'Two moments to revisit.' if len(selected) == 2 else 'One moment to revisit.'
    else:
        summary += 'Step through your moves, then try a king safety exercise.'
    if session.status == 'resignation':
        summary += ' This match ended by resignation.'
    node = None
    for ply in range(len(session.moves), 0, -1):
        node = MoveNode(str(session.moves[ply - 1]), comment=comments.get(ply, ''),
                        children=(node,) if node else ())
    root = MoveNode(comment=summary, children=(node,) if node else ())
    if session.status == 'checkmate':
        result = '0-1' if board.side_to_move == 'w' else '1-0'
    elif session.status == 'resignation':
        result = '0-1' if session.color == 'w' else '1-0'
    else:
        result = '1/2-1/2'
    game = GameRecord('review-' + session.match_id, root, result=result)
    entry = LibraryEntry(game, 'Your match with ' + session.opponent.name,
                         'beginner', ('match review',), summary, category='replay')
    return MatchReview(entry, selected,
                       selected[-1].practice_id if selected else 'chicky-king-safety')
