"""Persistent, offline character matches. The match owns its move history."""

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import random
import uuid

from .board import Board
from .challenge_commentary import VOICES
from .difficulty import DIFFICULTIES
from .moves import game_status, legal_moves
from .notation import to_fen
from .pieces import WHITE, BLACK


@dataclass(frozen=True)
class Opponent:
    ident: str
    name: str
    portrait: str
    strength: str
    preset: int = None
    depth_override: int = None
    random_move_chance: float = 0.0
    seconds_override: float = None

    @property
    def policy_parameters(self):
        if self.preset is None:
            return {"kind": "random", "revision": 1}
        name, seconds, depth = DIFFICULTIES[self.preset]
        if self.seconds_override is not None:
            seconds = self.seconds_override
        if self.depth_override is not None:
            depth = self.depth_override
        parameters = {"kind": "search", "preset": name, "seconds": seconds,
                      "depth": depth, "revision": 1}
        if self.random_move_chance:
            parameters["random_move_chance"] = self.random_move_chance
        return parameters


ROSTER = (
    Opponent("chicky", "Chicky", "chicky.bmp", "Beginner"),
    Opponent("pippa-pomeranian", "Pippa", "pomeranian.bmp", "Easy", 0, 1, 0.5),
    Opponent("tina-turtle", "Tina", "tina.bmp", "Gentle", 0, 1, 0.3),
    Opponent("tom-rabbit", "Tom", "tom.bmp", "Feisty", 1, 1, 0.1),
    Opponent("bruno-bear", "Bruno", "bruno.bmp", "Intermediate", 1, 2),
    Opponent("olive-owl", "Olivia", "olive.bmp", "Very good",
             preset=2, depth_override=32, seconds_override=2.0),
    Opponent("monty-cat", "Monty", "monty.bmp", "Strongest", 3),
)
OPPONENTS = {opponent.ident: opponent for opponent in ROSTER}


def stage_states(victories, legacy_access=()):
    """Derive all unlocks from verified (opponent ID, human colour) wins."""
    states = []
    unlocked = True
    for opponent in ROSTER:
        if not unlocked and opponent.ident not in legacy_access:
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
        if (session.opponent.preset is None and
                board.side_to_move != session.color and move != random.Random(
                    "{}:{}".format(session.move_seed, ply)).choice(options)):
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

    def stages(self):
        legacy_access = {row["opponent_id"] for row in self.connection.execute(
            "SELECT opponent_id FROM challenge_legacy_access")}
        return stage_states(self.victories(), legacy_access)

    def active(self):
        return self.connection.execute(
            "SELECT * FROM challenge_matches WHERE state = 'active' "
            "ORDER BY updated_at DESC LIMIT 1").fetchone()

    def award(self):
        return self.connection.execute(
            "SELECT * FROM challenge_awards WHERE award_id = 'uroschess-master'"
        ).fetchone()

    def mark_celebration_seen(self):
        with self.connection:
            self.connection.execute(
                """UPDATE challenge_awards SET celebration_seen_at = ?
                   WHERE award_id = 'uroschess-master'
                     AND celebration_seen_at IS NULL""", (_now(),))

    def start(self, color, opponent_id="chicky"):
        if (color not in (WHITE, BLACK) or opponent_id not in OPPONENTS or
                self.active() is not None):
            raise ValueError("Finish or discard the saved challenge first")
        opponent = OPPONENTS[opponent_id]
        required = self.stages()[ROSTER.index(opponent)]
        allowed = ({WHITE} if required == "white_required" else
                   {WHITE, BLACK} if required in ("black_required", "complete")
                   else set())
        if color not in allowed:
            raise ValueError("Beat earlier opponents with both colours first")
        session = ChallengeSession(self, uuid.uuid4().hex, color, opponent,
                                   random.SystemRandom().randrange(1 << 62),
                                   random.SystemRandom().randrange(1 << 62))
        self._save(session)
        return session

    def resume(self):
        row = self.active()
        if row is None:
            return None
        opponent = OPPONENTS.get(row["opponent_id"])
        if opponent is None or row["policy_revision"] != 1:
            raise ValueError("This saved match uses unsupported challenge rules")
        policy_row = self.connection.execute(
            "SELECT parameters_json FROM challenge_policies WHERE match_id = ?",
            (row["match_id"],)).fetchone()
        parameters = json.loads(policy_row[0]) if policy_row else {}
        if (parameters != opponent.policy_parameters and not
                (opponent.ident == "chicky" and parameters == {})):
            raise ValueError("This saved match uses an older opponent policy")
        session = ChallengeSession(self, row["match_id"], row["human_color"],
                                   opponent,
                                   row["move_seed"], row["comment_seed"])
        session.comment_id = row["comment_id"]
        try:
            for uci in json.loads(row["moves_json"]):
                move = _legal_uci(session.board, uci)
                if move is None or game_status(session.board) != "ongoing":
                    raise ValueError("Saved challenge has an invalid move")
                if (opponent.preset is None and
                        session.board.side_to_move != session.color and
                        move != random.Random("{}:{}".format(
                            session.move_seed, len(session.moves))).choice(
                                legal_moves(session.board))):
                    raise ValueError("Saved Chicky move violates its policy")
                session.board.make_move(move)
                session.moves.append(move)
            if (to_fen(session.board) != row["verified_fen"] or
                    game_status(session.board) != "ongoing"):
                raise ValueError("Saved challenge position cannot be verified")
            character_moves = (len(session.moves) +
                               (1 if session.color == BLACK else 0)) // 2
            if character_moves == 0:
                valid_comment = session.comment_id == "greeting"
            else:
                valid_comment = (session.comment_id.isdigit() and
                                 0 <= int(session.comment_id) <
                                 len(VOICES[opponent.ident].after_move))
            if not valid_comment:
                raise ValueError("Saved challenge commentary cannot be verified")
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
                """SELECT moves_json, state, opponent_id, human_color,
                          policy_revision FROM challenge_matches WHERE match_id = ?""",
                (session.match_id,)).fetchone()
            if old is not None and (old["state"] != "active" or
                                    old["opponent_id"] != session.opponent.ident or
                                    old["human_color"] != session.color or
                                    old["policy_revision"] != 1 or
                                    (len(json.loads(old["moves_json"])) >= len(session.moves)
                                     and not (result == "resignation" and
                                              len(json.loads(old["moves_json"])) ==
                                              len(session.moves)))):
                raise ValueError("Challenge match is no longer active")
            if old is not None:
                policy = self.connection.execute(
                    "SELECT parameters_json FROM challenge_policies WHERE match_id = ?",
                    (session.match_id,)).fetchone()
                params = json.loads(policy[0]) if policy else {}
                if params != session.opponent.policy_parameters and not (
                        session.opponent.ident == "chicky" and params == {}):
                    raise ValueError("Challenge policy changed during the match")
            self.connection.execute(
                """INSERT INTO challenge_matches
                   (match_id, opponent_id, human_color, policy_revision, state,
                    moves_json, verified_fen, move_seed, comment_seed, comment_id,
                    result, updated_at) VALUES (?, ?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(match_id) DO UPDATE SET
                     state=excluded.state, moves_json=excluded.moves_json,
                     verified_fen=excluded.verified_fen,
                     comment_id=excluded.comment_id, result=excluded.result,
                     updated_at=excluded.updated_at""",
                (session.match_id, session.opponent.ident, session.color, status,
                 json.dumps([str(move) for move in session.moves]),
                 to_fen(session.board), session.move_seed, session.comment_seed,
                 session.comment_id, result, now))
            if old is None:
                self.connection.execute(
                    "INSERT INTO challenge_policies VALUES (?, ?)",
                    (session.match_id, json.dumps(
                        session.opponent.policy_parameters, sort_keys=True)))
            if (result == "checkmate" and session.board.side_to_move != session.color
                    and _verified_result(session)):
                index = ROSTER.index(session.opponent)
                required = self.stages()[index]
                if (session.color == WHITE and required == "white_required" or
                        session.color == BLACK and required == "black_required"):
                    self.connection.execute(
                        """INSERT OR IGNORE INTO challenge_victories
                           (opponent_id, human_color, match_id, earned_at)
                           VALUES (?, ?, ?, ?)""",
                        (session.opponent.ident, session.color, session.match_id, now))
                    if all(state == "complete" for state in self.stages()):
                        self.connection.execute(
                            """INSERT OR IGNORE INTO challenge_awards
                               (award_id, earned_at, match_id, celebration_seen_at)
                               VALUES ('uroschess-master', ?, ?, NULL)""",
                            (now, session.match_id))


class ChallengeSession:
    def __init__(self, store, match_id, color, opponent, move_seed, comment_seed):
        self.store = store
        self.match_id = match_id
        self.color = color
        self.opponent = opponent
        self.move_seed = move_seed
        self.comment_seed = comment_seed
        self.board = Board()
        self.moves = []
        self.comment_id = "greeting"
        self.status = "ongoing"
        self.authorized_ai_move = None

    @property
    def comment(self):
        voice = VOICES[self.opponent.ident]
        if self.comment_id in ("greeting", "character_loses",
                               "character_wins", "draw"):
            return getattr(voice, self.comment_id)
        return voice.after_move[int(self.comment_id)]

    def choose_move(self):
        if self.opponent.preset is not None:
            raise ValueError("Search opponents choose moves in the AI worker")
        if self.status != "ongoing" or self.board.side_to_move == self.color:
            raise ValueError("It is not the opponent's turn")
        moves = legal_moves(self.board)
        return random.Random("{}:{}".format(
            self.move_seed, len(self.moves))).choice(moves)

    def choose_random_search_move(self):
        """Use the match seed to decide whether this search opponent slips up."""
        if (self.opponent.random_move_chance == 0 or
                self.status != "ongoing" or
                self.board.side_to_move == self.color):
            return None
        rng = random.Random("{}:{}:random".format(
            self.move_seed, len(self.moves)))
        if rng.random() >= self.opponent.random_move_chance:
            return None
        return rng.choice(legal_moves(self.board))

    def authorize_search_move(self, move):
        if (self.opponent.preset is None or self.status != "ongoing" or
                self.board.side_to_move == self.color or
                move not in legal_moves(self.board)):
            raise ValueError("Search result is not valid for this turn")
        self.authorized_ai_move = move

    def resign(self):
        if self.status != "ongoing":
            raise ValueError("This match has already ended")
        previous = self.comment_id
        self.comment_id = "character_wins"
        try:
            self.store._save(self, "resignation")
        except Exception:
            self.comment_id = previous
            raise
        self.status = "resignation"
        self.authorized_ai_move = None

    def accept(self, move, actor):
        if (self.status != "ongoing" or self.board.side_to_move != actor or
                move not in legal_moves(self.board)):
            raise ValueError("Move is not legal for this challenge turn")
        if actor != self.color:
            if self.opponent.preset is None and move != self.choose_move():
                raise ValueError("Move does not match Chicky's saved policy")
            if self.opponent.preset is not None and move != self.authorized_ai_move:
                raise ValueError("Move was not authorized by this search")
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
                order = list(range(len(VOICES[self.opponent.ident].after_move)))
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
        self.authorized_ai_move = None
        return result
