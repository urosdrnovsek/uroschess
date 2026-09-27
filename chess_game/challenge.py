"""Persistent, offline character matches. The match owns its move history."""

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import random
import uuid

from .board import Board
from .moves import game_status, legal_moves
from .notation import to_fen
from .pieces import WHITE, BLACK


@dataclass(frozen=True)
class Opponent:
    ident: str
    name: str
    portrait: str
    strength: str


ROSTER = (
    Opponent("chicky", "Chicky", "chicky.bmp", "Beginner"),
    Opponent("pippa-pomeranian", "Pippa", "pomeranian.bmp", "Easy"),
    Opponent("bruno-bear", "Bruno", "bruno.bmp", "Intermediate"),
    Opponent("olive-owl", "Olivia", "olive.bmp", "Very good"),
    Opponent("monty-cat", "Monty", "monty.bmp", "Strongest"),
)

CHICKY_LINES = (
    "I moved it! That was the important part.",
    "My tiny brain made a very big effort.",
    "Was that clever? I forgot to ask.",
    "Your turn! I shall practise looking wise.",
    "I had a plan. It flew away.",
    "That move used nearly all my feathers.",
    "I hope the pieces know what I am doing.",
    "Thinking is hungry work. Snack later?",
    "I am wearing my serious chess face.",
    "One move closer to becoming a legend. Maybe.",
)


def stage_states(victories):
    """Derive all unlocks from verified (opponent ID, human colour) wins."""
    states = []
    unlocked = True
    for opponent in ROSTER:
        if not unlocked:
            state = "locked"
        elif (opponent.ident, WHITE) not in victories:
            state = "white_required"
        elif (opponent.ident, BLACK) not in victories:
            state = "black_required"
        else:
            state = "complete"
        states.append(state)
        unlocked = state == "complete"
    return tuple(states)


def _now():
    return datetime.now(timezone.utc).isoformat()


def _legal_uci(board, uci):
    return next((move for move in legal_moves(board) if str(move) == uci), None)


def _verified_result(session):
    board = Board()
    for ply, move in enumerate(session.moves):
        options = legal_moves(board)
        if game_status(board) != "ongoing" or move not in options:
            return False
        if board.side_to_move != session.color and move != random.Random(
                "{}:{}".format(session.move_seed, ply)).choice(options):
            return False
        board.make_move(move)
    return to_fen(board) == to_fen(session.board) and game_status(board) == "checkmate"


class ChallengeStore:
    def __init__(self, progress_store):
        self.connection = progress_store.connection

    def victories(self):
        rows = self.connection.execute(
            "SELECT opponent_id, human_color FROM challenge_victories").fetchall()
        return {(row["opponent_id"], row["human_color"]) for row in rows}

    def active(self):
        return self.connection.execute(
            "SELECT * FROM challenge_matches WHERE state = 'active' "
            "ORDER BY updated_at DESC LIMIT 1").fetchone()

    def start(self, color):
        if color not in (WHITE, BLACK) or self.active() is not None:
            raise ValueError("Finish or discard the saved challenge first")
        required = stage_states(self.victories())[0]
        allowed = ({WHITE} if required == "white_required" else
                   {WHITE, BLACK} if required in ("black_required", "complete")
                   else set())
        if color not in allowed:
            raise ValueError("Chicky must be beaten with White, then Black")
        session = ChallengeSession(self, uuid.uuid4().hex, color,
                                   random.SystemRandom().randrange(1 << 62),
                                   random.SystemRandom().randrange(1 << 62))
        self._save(session)
        return session

    def resume(self):
        row = self.active()
        if row is None:
            return None
        if row["opponent_id"] != "chicky" or row["policy_revision"] != 1:
            raise ValueError("This saved match uses unsupported challenge rules")
        session = ChallengeSession(self, row["match_id"], row["human_color"],
                                   row["move_seed"], row["comment_seed"])
        session.comment_id = row["comment_id"]
        try:
            for uci in json.loads(row["moves_json"]):
                move = _legal_uci(session.board, uci)
                if move is None or game_status(session.board) != "ongoing":
                    raise ValueError("Saved challenge has an invalid move")
                session.board.make_move(move)
                session.moves.append(move)
            if (to_fen(session.board) != row["verified_fen"] or
                    game_status(session.board) != "ongoing"):
                raise ValueError("Saved challenge position cannot be verified")
        except (TypeError, json.JSONDecodeError, KeyError) as error:
            raise ValueError("Saved challenge cannot be verified") from error
        return session

    def discard(self, match_id):
        with self.connection:
            self.connection.execute(
                "UPDATE challenge_matches SET state = 'abandoned', updated_at = ? "
                "WHERE match_id = ? AND state = 'active'", (_now(), match_id))

    def _save(self, session, result=None):
        """Publish one move and its possible victory in one transaction."""
        status = "finished" if result is not None else "active"
        now = _now()
        with self.connection:
            old = self.connection.execute(
                "SELECT moves_json, state FROM challenge_matches WHERE match_id = ?",
                (session.match_id,)).fetchone()
            if old is not None and (old["state"] != "active" or
                                    len(json.loads(old["moves_json"])) > len(session.moves)):
                raise ValueError("Challenge match is no longer active")
            self.connection.execute(
                """INSERT INTO challenge_matches
                   (match_id, opponent_id, human_color, policy_revision, state,
                    moves_json, verified_fen, move_seed, comment_seed, comment_id,
                    result, updated_at) VALUES (?, 'chicky', ?, 1, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(match_id) DO UPDATE SET
                     state=excluded.state, moves_json=excluded.moves_json,
                     verified_fen=excluded.verified_fen,
                     comment_id=excluded.comment_id, result=excluded.result,
                     updated_at=excluded.updated_at""",
                (session.match_id, session.color, status,
                 json.dumps([str(move) for move in session.moves]),
                 to_fen(session.board), session.move_seed, session.comment_seed,
                 session.comment_id, result, now))
            if (result == "checkmate" and session.board.side_to_move != session.color
                    and _verified_result(session)):
                required = stage_states(self.victories())[0]
                if (session.color == WHITE and required == "white_required" or
                        session.color == BLACK and required == "black_required"):
                    self.connection.execute(
                        """INSERT OR IGNORE INTO challenge_victories
                           (opponent_id, human_color, match_id, earned_at)
                           VALUES ('chicky', ?, ?, ?)""",
                        (session.color, session.match_id, now))


class ChallengeSession:
    def __init__(self, store, match_id, color, move_seed, comment_seed):
        self.store = store
        self.match_id = match_id
        self.color = color
        self.move_seed = move_seed
        self.comment_seed = comment_seed
        self.board = Board()
        self.moves = []
        self.comment_id = "greeting"
        self.status = "ongoing"

    @property
    def comment(self):
        if self.comment_id == "greeting":
            return "Hello! I think I know how the pieces move."
        if self.comment_id == "character_loses":
            return "I think my crown is still in the egg."
        if self.comment_id == "character_wins":
            return "Oh! Did I win? My feathers are surprised."
        if self.comment_id == "draw":
            return "A draw! We both get to keep our crowns."
        return CHICKY_LINES[int(self.comment_id)]

    def choose_move(self):
        if self.status != "ongoing" or self.board.side_to_move == self.color:
            raise ValueError("It is not Chicky's turn")
        moves = legal_moves(self.board)
        return random.Random("{}:{}".format(
            self.move_seed, len(self.moves))).choice(moves)

    def accept(self, move, actor):
        if (self.status != "ongoing" or self.board.side_to_move != actor or
                move not in legal_moves(self.board)):
            raise ValueError("Move is not legal for this challenge turn")
        if actor != self.color and move != self.choose_move():
            raise ValueError("Move does not match Chicky's saved policy")
        candidate = self.board.clone()
        candidate.make_move(move)
        result = game_status(candidate)
        previous = self.comment_id
        if actor != self.color:
            if result == "checkmate":
                self.comment_id = "character_wins"
            elif result != "ongoing":
                self.comment_id = "draw"
            else:
                order = list(range(len(CHICKY_LINES)))
                random.Random(self.comment_seed).shuffle(order)
                # Character moves are every other ply, starting at 0 or 1.
                index = (len(self.moves) - (1 if self.color == WHITE else 0)) // 2
                self.comment_id = str(order[index % len(order)])
                if self.comment_id == previous:
                    self.comment_id = str(order[(index + 1) % len(order)])
        elif result == "checkmate":
            self.comment_id = "character_loses"
        elif result != "ongoing":
            self.comment_id = "draw"
        self.moves.append(move)
        try:
            old_board = self.board
            self.board = candidate
            self.store._save(self, None if result == "ongoing" else result)
        except Exception:
            self.board = old_board
            self.moves.pop()
            self.comment_id = previous
            raise
        self.status = result
        return result
