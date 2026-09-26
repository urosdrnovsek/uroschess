"""UI-independent data contracts for games and teaching content."""

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping, Optional, Tuple


def _frozen_mapping(values=None):
    return MappingProxyType(dict(values or {}))


@dataclass(frozen=True)
class SourceInfo:
    """Where imported moves or authored commentary came from."""

    name: str
    url: str = ""
    license: str = ""
    attribution: str = ""


@dataclass(frozen=True)
class MoveNode:
    """One immutable node in an annotated game tree.

    ``uci`` is the move from the parent to this node. The root has no UCI move.
    The first child is the main line; later children are alternatives.
    """

    uci: Optional[str] = None
    comment: str = ""
    starting_comment: str = ""
    nags: Tuple[int, ...] = ()
    children: Tuple["MoveNode", ...] = ()

    @property
    def main_line(self):
        return self.children[0] if self.children else None


@dataclass(frozen=True)
class GameRecord:
    """A recorded game and its immutable annotated move tree."""

    game_id: str
    root: MoveNode
    headers: Mapping[str, str] = field(default_factory=_frozen_mapping)
    starting_fen: Optional[str] = None
    result: str = "*"
    source: Optional[SourceInfo] = None

    def __post_init__(self):
        if not self.game_id.strip():
            raise ValueError("game_id must not be empty")
        object.__setattr__(self, "headers", _frozen_mapping(self.headers))
        if self.root.uci is not None:
            raise ValueError("the game-tree root cannot contain a move")
        if self.result not in ("1-0", "0-1", "1/2-1/2", "*"):
            raise ValueError("unsupported game result: " + self.result)


_SQUARE_FILES = "abcdefgh"


def _validate_square(value, field_name):
    if (not isinstance(value, str) or len(value) != 2
            or value[0] not in _SQUARE_FILES or value[1] not in "12345678"):
        raise ValueError("{} must be a chess square".format(field_name))


@dataclass(frozen=True)
class BoardArrow:
    """A semantic board arrow authored as algebraic square names."""

    from_square: str
    to_square: str
    role: str = "idea"

    def __post_init__(self):
        _validate_square(self.from_square, "arrow from_square")
        _validate_square(self.to_square, "arrow to_square")
        if self.role not in ("idea", "move", "warning"):
            raise ValueError("unsupported arrow role: " + self.role)


@dataclass(frozen=True)
class SquareHighlight:
    """A semantic square highlight that remains understandable by shape."""

    square: str
    role: str = "focus"

    def __post_init__(self):
        _validate_square(self.square, "highlight square")
        if self.role not in ("focus", "target", "warning"):
            raise ValueError("unsupported highlight role: " + self.role)


@dataclass(frozen=True)
class MoveAnswer:
    """One reviewed learner move and its authored result."""

    uci: str
    outcome: str
    feedback: str
    reply_moves: Tuple[str, ...] = ()

    def __post_init__(self):
        if len(self.uci) not in (4, 5):
            raise ValueError("answer uci must contain four or five characters")
        if self.outcome not in ("preferred", "acceptable", "wrong"):
            raise ValueError("unsupported answer outcome: " + self.outcome)
        if not self.feedback.strip():
            raise ValueError("answer feedback must not be empty")


@dataclass(frozen=True)
class ReviewedMove:
    """One move in a finite, authored learner/opponent exercise tree."""

    uci: str
    role: str
    outcome: str
    feedback: str = ""
    children: Tuple["ReviewedMove", ...] = ()
    next_prompt: str = ""
    hints: Tuple[str, ...] = ()

    def __post_init__(self):
        def has_success(nodes):
            return any(
                node.outcome in ("preferred", "acceptable")
                or has_success(node.children)
                for node in nodes)

        if len(self.uci) not in (4, 5):
            raise ValueError("reviewed-tree uci must contain four or five characters")
        if self.role not in ("learner", "opponent"):
            raise ValueError("reviewed-tree role must be learner or opponent")
        allowed = ({"continue", "preferred", "acceptable", "wrong"}
                   if self.role == "learner" else {"reply"})
        if self.outcome not in allowed:
            raise ValueError(
                "unsupported {} outcome: {}".format(self.role, self.outcome))
        if self.role == "learner" and not self.feedback.strip():
            raise ValueError("learner tree moves require feedback")
        if self.role == "learner" and self.outcome == "continue":
            if not self.children or any(
                    child.role != "opponent" for child in self.children):
                raise ValueError(
                    "a continuing learner move requires opponent replies")
            if any(not has_success((child,)) for child in self.children):
                raise ValueError(
                    "every opponent reply must lead to a successful answer")
        elif self.role == "opponent":
            if not self.children or any(
                    child.role != "learner" for child in self.children):
                raise ValueError(
                    "an opponent reply requires one or more learner choices")
            if not has_success(self.children):
                raise ValueError(
                    "an opponent reply must retain a successful learner choice")
        elif self.children:
            raise ValueError("terminal reviewed-tree moves cannot have children")
        moves = [child.uci for child in self.children]
        if len(moves) != len(set(moves)):
            raise ValueError("reviewed-tree sibling moves must be unique")


@dataclass(frozen=True)
class LessonQuestion:
    """A reviewed prediction prompt whose answer is attempted on the board."""

    prompt: str
    answers: Tuple[MoveAnswer, ...] = ()
    hints: Tuple[str, ...] = ()
    kind: str = "move"
    timing: str = "before_move"
    evaluator: str = "reviewed_moves"
    other_legal_move_text: str = (
        "That move is legal, but it is not covered by this exercise. "
        "Explore it, then return to the lesson.")
    tree: Tuple[ReviewedMove, ...] = ()

    def __post_init__(self):
        if not self.prompt.strip():
            raise ValueError("question prompt must not be empty")
        if self.kind != "move" or self.timing not in ("before_move", "after_move"):
            raise ValueError("unsupported lesson question kind or timing")
        if self.evaluator not in ("reviewed_moves", "reviewed_tree"):
            raise ValueError("unsupported question evaluator: " + self.evaluator)
        choices = self.answers if self.evaluator == "reviewed_moves" else self.tree
        if not choices:
            raise ValueError("a reviewed question requires authored choices")
        if self.evaluator == "reviewed_moves" and self.tree:
            raise ValueError("reviewed_moves questions cannot contain a tree")
        if self.evaluator == "reviewed_tree":
            if self.answers:
                raise ValueError("reviewed_tree questions cannot contain answers")
            if any(node.role != "learner" for node in self.tree):
                raise ValueError("reviewed-tree roots must be learner moves")
        moves = [choice.uci for choice in choices]
        if len(moves) != len(set(moves)):
            raise ValueError("question answer moves must be unique")
        if self.evaluator == "reviewed_moves":
            successful = any(answer.outcome in ("preferred", "acceptable")
                             for answer in self.answers)
        else:
            def has_success(nodes):
                return any(
                    node.outcome in ("preferred", "acceptable")
                    or has_success(node.children)
                    for node in nodes)
            successful = has_success(self.tree)
        if not successful:
            raise ValueError("a question requires a successful answer")


@dataclass(frozen=True)
class LessonStep:
    """A teaching moment tied to an exact source-game position."""

    step_id: str
    node_path: Tuple[str, ...]
    expected_fen: str
    explanation: str
    detail: str = ""
    arrows: Tuple[BoardArrow, ...] = ()
    highlights: Tuple[SquareHighlight, ...] = ()
    question: Optional[LessonQuestion] = None
    coach_prompt: str = ""
    practice_mode: str = "guided"

    def __post_init__(self):
        if not self.step_id.strip():
            raise ValueError("step_id must not be empty")
        if not self.expected_fen.strip():
            raise ValueError("expected_fen must not be empty")
        if self.practice_mode not in ("guided", "independent"):
            raise ValueError("practice_mode must be guided or independent")


@dataclass(frozen=True)
class Lesson:
    """A versioned sequence of teaching steps for one source game."""

    lesson_id: str
    content_revision: int
    title: str
    level: str
    estimated_minutes: int
    objective: str
    game_id: str
    steps: Tuple[LessonStep, ...]
    concepts: Tuple[str, ...] = ()
    takeaway: str = ""
    schema_version: int = 1
    prerequisites: Tuple[str, ...] = ()
    commentary_source: Optional[SourceInfo] = None
    coach_player_id: str = ""
    content_kind: str = "synthetic"
    related_source_game_id: str = ""
    initial_help: bool = False

    def __post_init__(self):
        if not self.lesson_id.strip() or not self.game_id.strip():
            raise ValueError("lesson_id and game_id must not be empty")
        if self.schema_version not in (1, 2, 3):
            raise ValueError("unsupported lesson schema version")
        if self.content_kind not in ("synthetic", "historical"):
            raise ValueError("unsupported lesson content kind")
        if self.content_revision < 1:
            raise ValueError("content_revision must be at least 1")
        if self.level not in ("beginner", "intermediate"):
            raise ValueError("level must be beginner or intermediate")
        if self.estimated_minutes < 1:
            raise ValueError("estimated_minutes must be positive")
        if not self.steps:
            raise ValueError("lesson must contain at least one step")
        ids = [step.step_id for step in self.steps]
        if len(ids) != len(set(ids)):
            raise ValueError("lesson step IDs must be unique")
