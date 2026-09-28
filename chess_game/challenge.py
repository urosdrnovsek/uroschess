"""Persistent, offline character matches. The match owns its move history."""

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import random
import uuid
from pathlib import Path

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

RECOVERY_MESSAGES = {
    "malformed_history": "The saved move history cannot be read.",
    "invalid_history": "The saved moves are not a legal match history.",
    "position_mismatch": "The saved position does not match its moves.",
    "unsupported_policy": "This saved match uses an older opponent policy.",
    "unsupported_opponent": "This saved match uses an unknown opponent.",
    "invalid_metadata": "The saved match details cannot be verified.",
    "invalid_commentary": "The saved commentary does not match the moves.",
}


@dataclass(frozen=True)
class ChallengeVerification:
    match_id: str
    reason: str = None
    session: object = None

    @property
    def valid(self):
        return self.reason is None


@dataclass(frozen=True)
class MedalSummary:
    win_count: int
    small_portraits: int
    gold_portrait: bool
    label: str


def medal_summary(win_count):
    if not isinstance(win_count, int) or win_count < 0:
        raise ValueError("Win count must be a nonnegative integer")
    if win_count == 0:
        return MedalSummary(0, 0, False, "No medals yet")
    if win_count < 10:
        return MedalSummary(win_count, win_count, False,
                            "{} {}".format(win_count, "medal" if win_count == 1
                                           else "medals"))
    return MedalSummary(win_count, 0, True,
                        "Gold medal · {} lifetime wins".format(win_count))


class ChallengeSaveError(ValueError):
    def __init__(self, result):
        self.result = result
        super().__init__(RECOVERY_MESSAGES[result.reason])


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


def verify_historical_win(row, policy_row):
    """Check retained terminal evidence without replaying timed search decisions."""
    opponent = OPPONENTS.get(row["opponent_id"])
    if (opponent is None or row["state"] != "finished" or
            row["result"] != "checkmate" or row["policy_revision"] != 1 or
            row["human_color"] not in (WHITE, BLACK) or
            row["comment_id"] != "character_loses" or
            not isinstance(row["move_seed"], int) or
            not isinstance(row["comment_seed"], int)):
        return False
    try:
        parameters = json.loads(policy_row["parameters_json"]) if policy_row else {}
        history = json.loads(row["moves_json"])
    except (TypeError, ValueError, RecursionError):
        return False
    if (parameters != opponent.policy_parameters and not
            (opponent.ident == "chicky" and parameters == {})):
        return False
    if (not isinstance(history, list) or not history or
            any(not isinstance(uci, str) or len(uci) not in (4, 5)
                for uci in history)):
        return False
    board = Board()
    for ply, uci in enumerate(history):
        if game_status(board) != "ongoing":
            return False
        options = legal_moves(board)
        move = next((item for item in options if str(item) == uci), None)
        if move is None:
            return False
        if (opponent.preset is None and board.side_to_move != row["human_color"]
                and move != random.Random("{}:{}".format(
                    row["move_seed"], ply)).choice(options)):
            return False
        board.make_move(move)
    return (to_fen(board) == row["verified_fen"] and
            game_status(board) == "checkmate" and
            board.side_to_move != row["human_color"])


def verify_saved_match(row, policy_row, store):
    """Reconstruct an active match without changing its record or awarding wins."""
    match_id = row["match_id"]

    def invalid(reason):
        return ChallengeVerification(match_id, reason)

    opponent = OPPONENTS.get(row["opponent_id"])
    if opponent is None:
        return invalid("unsupported_opponent")
    if (row["policy_revision"] != 1 or
            (policy_row is None and opponent.ident != "chicky")):
        return invalid("unsupported_policy")
    try:
        parameters = json.loads(policy_row["parameters_json"]) if policy_row else {}
    except (TypeError, ValueError, RecursionError):
        return invalid("unsupported_policy")
    if (parameters != opponent.policy_parameters and not
            (opponent.ident == "chicky" and parameters == {})):
        return invalid("unsupported_policy")
    if (row["state"] != "active" or row["result"] is not None or
            row["human_color"] not in (WHITE, BLACK) or
            not isinstance(row["move_seed"], int) or
            not isinstance(row["comment_seed"], int) or
            not isinstance(row["comment_id"], str) or
            not isinstance(row["verified_fen"], str)):
        return invalid("invalid_metadata")
    try:
        history = json.loads(row["moves_json"])
    except (TypeError, ValueError, RecursionError):
        return invalid("malformed_history")
    if (not isinstance(history, list) or
            any(not isinstance(uci, str) or len(uci) not in (4, 5)
                for uci in history)):
        return invalid("malformed_history")

    session = ChallengeSession(store, match_id, row["human_color"], opponent,
                               row["move_seed"], row["comment_seed"])
    expected_comment = "greeting"
    for uci in history:
        if game_status(session.board) != "ongoing":
            return invalid("invalid_history")
        options = legal_moves(session.board)
        move = next((item for item in options if str(item) == uci), None)
        if move is None:
            return invalid("invalid_history")
        actor = session.board.side_to_move
        if (opponent.preset is None and actor != session.color and
                move != random.Random("{}:{}".format(
                    session.move_seed, len(session.moves))).choice(options)):
            return invalid("unsupported_policy")
        session.board.make_move(move)
        if actor != session.color and game_status(session.board) == "ongoing":
            order = list(range(len(VOICES[opponent.ident].after_move)))
            random.Random(session.comment_seed).shuffle(order)
            index = (len(session.moves) -
                     (1 if session.color == WHITE else 0)) // 2
            current = str(order[index % len(order)])
            expected_comment = (str(order[(index + 1) % len(order)])
                                if current == expected_comment else current)
        session.moves.append(move)
    if (to_fen(session.board) != row["verified_fen"] or
            game_status(session.board) != "ongoing"):
        return invalid("position_mismatch")
    if row["comment_id"] != expected_comment:
        return invalid("invalid_commentary")
    session.comment_id = expected_comment
    return ChallengeVerification(match_id, session=session)


class ChallengeStore:
    def __init__(self, progress_store):
        self.connection = progress_store.connection

    def victories(self):
        rows = self.connection.execute(
            "SELECT opponent_id, human_color FROM challenge_victories").fetchall()
        return {(row["opponent_id"], row["human_color"]) for row in rows}

    def medal_counts(self):
        counts = {opponent.ident: 0 for opponent in ROSTER}
        for row in self.connection.execute(
                "SELECT opponent_id, COUNT(*) AS total FROM challenge_win_events "
                "GROUP BY opponent_id"):
            if row["opponent_id"] in counts:
                counts[row["opponent_id"]] = row["total"]
        return counts

    def reward_for_match(self, match_id):
        event = self.connection.execute(
            "SELECT opponent_id, human_color FROM challenge_win_events "
            "WHERE match_id = ?", (match_id,)).fetchone()
        if event is None:
            return None
        badge = self.connection.execute(
            "SELECT match_id FROM challenge_victories WHERE opponent_id = ? "
            "AND human_color = ?", (event["opponent_id"],
                                  event["human_color"])).fetchone()
        return {"medal": True, "new_badge": badge is not None and
                badge["match_id"] == match_id}

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
        result = self.inspect_active()
        if result is None:
            return None
        if not result.valid:
            raise ChallengeSaveError(result)
        return result.session

    def inspect_active(self):
        row = self.active()
        if row is None:
            return None
        policy_row = self.connection.execute(
            "SELECT parameters_json FROM challenge_policies WHERE match_id = ?",
            (row["match_id"],)).fetchone()
        return verify_saved_match(row, policy_row, self)

    def archive_invalid(self, match_id):
        """Clear an invalid active slot while retaining its original evidence."""
        with self.connection:
            self.connection.execute("BEGIN IMMEDIATE")
            row = self.active()
            if row is None or row["match_id"] != match_id:
                raise ValueError("This saved match is no longer active")
            policy_row = self.connection.execute(
                "SELECT parameters_json FROM challenge_policies WHERE match_id = ?",
                (match_id,)).fetchone()
            result = verify_saved_match(row, policy_row, self)
            if result.valid:
                raise ValueError("This match is valid; resume or discard it")
            now = _now()
            self.connection.execute(
                """INSERT INTO challenge_recovery
                   (match_id, reason_code, diagnosed_at, archived_at,
                    original_updated_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (match_id, result.reason, now, now, row["updated_at"]))
            updated = self.connection.execute(
                """UPDATE challenge_matches SET state = 'abandoned', updated_at = ?
                   WHERE match_id = ? AND state = 'active'""", (now, match_id))
            if updated.rowcount != 1:
                raise ValueError("This saved match is no longer active")
        return result

    def archived_recoveries(self):
        return self.connection.execute(
            """SELECT recovery.match_id, recovery.reason_code,
                      recovery.archived_at, matches.opponent_id
               FROM challenge_recovery AS recovery
               JOIN challenge_matches AS matches ON matches.match_id = recovery.match_id
               ORDER BY recovery.archived_at DESC, recovery.match_id DESC""").fetchall()

    def export_match(self, match_id, destination):
        """Copy the raw saved record to a new local JSON file."""
        row = self.connection.execute(
            "SELECT * FROM challenge_matches WHERE match_id = ?",
            (match_id,)).fetchone()
        if row is None:
            raise ValueError("Saved challenge match was not found")
        policy = self.connection.execute(
            "SELECT * FROM challenge_policies WHERE match_id = ?",
            (match_id,)).fetchone()
        recovery = self.connection.execute(
            "SELECT * FROM challenge_recovery WHERE match_id = ?",
            (match_id,)).fetchone()
        original = dict(row)
        if recovery is not None:
            original["state"] = "active"
            original["updated_at"] = recovery["original_updated_at"]
        payload = {"format": "uroschess-challenge-recovery-1",
                   "match": dict(row), "policy": dict(policy) if policy else None,
                   "recovery": dict(recovery) if recovery else None,
                   "original_match": original}
        path = Path(destination)
        with path.open("x", encoding="utf-8") as target:
            json.dump(payload, target, indent=2, sort_keys=True)
            target.write("\n")
        return path

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
                self.connection.execute(
                    """INSERT INTO challenge_win_events
                       (match_id, opponent_id, human_color, earned_at,
                        verification_revision) VALUES (?, ?, ?, ?, 1)""",
                    (session.match_id, session.opponent.ident, session.color, now))
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
