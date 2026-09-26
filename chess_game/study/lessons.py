"""Validation and state transitions for guided lessons."""

from dataclasses import dataclass

from .chess_adapter import ChessAdapter, MoveResolutionError


READING = "READING"
QUESTION = "QUESTION"
FEEDBACK = "FEEDBACK"
EXPLORING = "EXPLORING"
COMPLETED = "COMPLETED"


class LessonValidationError(ValueError):
    """Authored lesson data does not match its immutable source game."""


class LessonStateError(ValueError):
    """An action is unavailable in the lesson's current state."""


@dataclass(frozen=True)
class ResolvedLessonStep:
    step: object
    replay_path: tuple


@dataclass(frozen=True)
class AttemptResult:
    outcome: str
    feedback: str
    uci: str = ""
    move: object = None


@dataclass
class _ExplorationSnapshot:
    state: str
    board: object
    last_attempt: object
    step_solved: bool
    assisted: bool
    view_state: object
    tree_choices: tuple
    active_prompt: str
    active_hints: tuple


def resolve_lesson(game, lesson, adapter=None):
    """Resolve every authored UCI path and verify its exact expected FEN."""
    adapter = adapter or ChessAdapter()
    prefix = "game {!r}, lesson {!r}".format(game.game_id, lesson.lesson_id)
    if lesson.game_id != game.game_id:
        raise LessonValidationError(
            "{}: lesson references game {!r}".format(prefix, lesson.game_id))

    def validate_tree(nodes, board, context, path=()):
        for index, node in enumerate(nodes):
            branch = path + (index,)
            branch_board = board.clone()
            try:
                adapter.apply_uci(branch_board, node.uci)
            except MoveResolutionError as error:
                location = ".".join(str(value) for value in branch)
                raise LessonValidationError(
                    "{}: invalid reviewed-tree move {!r} at branch {}: {}".format(
                        context, node.uci, location, error)) from error
            if node.children:
                validate_tree(node.children, branch_board, context, branch)

    resolved = []
    previous_ply = -1
    for step in lesson.steps:
        context = "{}, step {!r}".format(prefix, step.step_id)
        board = (adapter.from_fen(game.starting_fen) if game.starting_fen
                 else adapter.initial_board())
        node = game.root
        replay_path = []
        for ply, uci in enumerate(step.node_path, 1):
            matches = [(index, child) for index, child in enumerate(node.children)
                       if child.uci == uci]
            if len(matches) != 1:
                raise LessonValidationError(
                    "{}: cannot resolve move {!r} at path ply {}".format(
                        context, uci, ply))
            child_index, node = matches[0]
            replay_path.append(child_index)
            try:
                adapter.apply_uci(board, uci)
            except MoveResolutionError as error:
                raise LessonValidationError("{}: {}".format(context, error)) from error

        actual_fen = adapter.fen(board)
        if actual_fen != step.expected_fen:
            raise LessonValidationError(
                "{}: expected FEN {!r}, got {!r}".format(
                    context, step.expected_fen, actual_fen))
        if len(step.node_path) <= previous_ply:
            raise LessonValidationError(
                "{}: lesson steps must follow source-game order".format(context))
        previous_ply = len(step.node_path)

        if step.question:
            if step.question.evaluator == "reviewed_tree":
                if lesson.schema_version < 2:
                    raise LessonValidationError(
                        "{}: reviewed_tree requires lesson schema version 2".format(
                            context))
                validate_tree(step.question.tree, board, context)
            else:
                for answer in step.question.answers:
                    answer_board = board.clone()
                    try:
                        adapter.apply_uci(answer_board, answer.uci)
                        for reply in answer.reply_moves:
                            adapter.apply_uci(answer_board, reply)
                    except MoveResolutionError as error:
                        raise LessonValidationError(
                            "{}: invalid reviewed line beginning {!r}: {}".format(
                                context, answer.uci, error)) from error
        resolved.append(ResolvedLessonStep(step, tuple(replay_path)))
    return tuple(resolved)


class LessonController:
    """UI-independent guided-lesson state machine.

    Source-game positions are always rebuilt through ``ReplayController``.
    Learner attempts and exploration use private board clones, so neither can
    mutate the game tree or the saved question position.
    """

    def __init__(self, game, lesson, adapter=None, resume_step=0,
                 progress_totals=None, completed=False, step_progress=None,
                 resume_assisted=False):
        from .replay import ReplayController

        self.game = game
        self.lesson = lesson
        self.adapter = adapter or ChessAdapter()
        self.resolved_steps = resolve_lesson(game, lesson, self.adapter)
        if not 0 <= resume_step < len(self.resolved_steps):
            resume_step = 0
        self.replay = ReplayController(game, self.adapter)
        self.step_index = resume_step
        self.state = COMPLETED if completed else READING
        totals = progress_totals or {}
        self.attempts = int(totals.get("attempts", 0))
        self.hints_used = int(totals.get("hints_used", 0))
        self.reveals = int(totals.get("reveals", 0))
        self.successes = int(totals.get("successes", 0))
        self.step_progress = {
            step_id: {"attempts": record.attempts,
                      "hints_used": record.hints_used,
                      "reveals": record.reveals,
                      "outcome": record.outcome}
            for step_id, record in (step_progress or {}).items()}
        self._hint_index = 0
        self._last_attempt = None
        self._step_solved = False
        self._assisted = bool(resume_assisted and not completed)
        self._exploration_snapshot = None
        self._display_board = None
        self._tree_choices = ()
        self._active_prompt = ""
        self._active_hints = ()
        self._load_step_position()

    @property
    def current_step(self):
        return self.resolved_steps[self.step_index].step

    @property
    def board(self):
        return self._display_board.clone()

    @property
    def last_attempt(self):
        return self._last_attempt

    @property
    def active_prompt(self):
        return self._active_prompt or (
            self.current_step.question.prompt if self.current_step.question else "")

    @property
    def step_solved(self):
        return self._step_solved

    @property
    def assisted(self):
        return self._assisted

    @property
    def future_source_hidden(self):
        question = self.current_step.question
        return bool(question and question.timing == "before_move"
                    and not self._step_solved)

    @property
    def visible_arrows(self):
        return self.current_step.arrows if self._answer_overlay_visible() else ()

    @property
    def visible_highlights(self):
        return (self.current_step.highlights
                if self._answer_overlay_visible() else ())

    def _answer_overlay_visible(self):
        if not self.current_step.question:
            return True
        return (self.state == FEEDBACK and self._last_attempt is not None
                and self._last_attempt.outcome in
                ("preferred", "acceptable", "revealed"))

    def _load_step_position(self):
        self.replay.jump(self.resolved_steps[self.step_index].replay_path)
        self._display_board = self.replay.board
        self._tree_choices = ()
        self._active_prompt = (
            self.current_step.question.prompt if self.current_step.question else "")
        self._active_hints = (
            self.current_step.question.hints if self.current_step.question else ())

    def begin_question(self):
        if self.state != READING or not self.current_step.question:
            raise LessonStateError("no question can be started now")
        self.state = QUESTION
        self._display_board = self.replay.board
        question = self.current_step.question
        self._tree_choices = (question.tree
                              if question.evaluator == "reviewed_tree" else ())
        self._active_prompt = question.prompt
        self._active_hints = question.hints
        return True

    def request_hint(self):
        if self.state not in (QUESTION, FEEDBACK):
            raise LessonStateError("hints are available while answering")
        hints = self._active_hints
        if not hints:
            return "No hint is available for this question."
        index = min(self._hint_index, len(hints) - 1)
        if self._hint_index < len(hints):
            self._hint_index += 1
            self.hints_used += 1
            self._assisted = True
            self._step_record()["hints_used"] += 1
        return hints[index]

    def _step_record(self):
        return self.step_progress.setdefault(
            self.current_step.step_id,
            {"attempts": 0, "hints_used": 0,
             "reveals": 0, "outcome": "unresolved"})

    def _mark_step_solved(self):
        record = self._step_record()
        record["outcome"] = "helped" if self._assisted else "independent"

    def attempt_uci(self, uci, view_state=None):
        if self.state != QUESTION:
            raise LessonStateError("moves can only be answered in QUESTION state")
        question = self.current_step.question
        question_board = self._display_board.clone()
        attempt_board = question_board.clone()
        try:
            learner_move, _san = self.adapter.apply_uci(attempt_board, uci)
        except MoveResolutionError:
            result = AttemptResult("illegal", "That move is not legal here.", uci)
            self._last_attempt = result
            return result

        self.attempts += 1
        self._step_record()["attempts"] += 1
        choices = (self._tree_choices if question.evaluator == "reviewed_tree"
                   else question.answers)
        answer = next((item for item in choices if item.uci == uci), None)
        if answer is None:
            snapshot = _ExplorationSnapshot(
                QUESTION, question_board, self._last_attempt,
                self._step_solved, self._assisted, view_state,
                tuple(self._tree_choices), self._active_prompt,
                self._active_hints)
            self._exploration_snapshot = snapshot
            self._display_board = attempt_board
            self.state = EXPLORING
            result = AttemptResult(
                "not_covered",
                "That move is okay to try. This lesson is looking for a different "
                "idea. Choose Return to lesson to try again.",
                uci, learner_move)
            self._last_attempt = result
            return result

        if question.evaluator == "reviewed_tree" and answer.outcome == "continue":
            reply = answer.children[0]
            reply_side = ("White" if attempt_board.side_to_move == "w"
                          else "Black")
            reply_move, reply_san = self.adapter.apply_uci(
                attempt_board, reply.uci)
            self._tree_choices = reply.children
            self._active_prompt = reply.next_prompt or question.prompt
            if reply.hints:
                self._active_hints = reply.hints
                self._hint_index = 0
            feedback = answer.feedback + " {} just played {}. Your turn again.".format(
                reply_side, reply_san)
            if reply.feedback:
                feedback += " " + reply.feedback
            result = AttemptResult("continue", feedback, uci, reply_move)
            self._display_board = attempt_board
            self._last_attempt = result
            return result

        result = AttemptResult(answer.outcome, answer.feedback, uci, learner_move)
        self._display_board = attempt_board
        self._last_attempt = result
        self.state = FEEDBACK
        if answer.outcome in ("preferred", "acceptable"):
            self._step_solved = True
            self.successes += 1
            self._mark_step_solved()
        return result

    def retry(self):
        if self.state != FEEDBACK or not self._last_attempt:
            raise LessonStateError("there is no answer to retry")
        if self._last_attempt.outcome in ("preferred", "acceptable", "revealed"):
            raise LessonStateError("a successful answer does not need a retry")
        self.state = QUESTION
        self._last_attempt = None
        self._display_board = self.replay.board
        question = self.current_step.question
        self._tree_choices = (question.tree
                              if question.evaluator == "reviewed_tree" else ())
        self._active_prompt = question.prompt
        self._active_hints = question.hints
        return True

    @staticmethod
    def _successful_tree_line(nodes, wanted):
        for node in nodes:
            if node.outcome == wanted:
                return (node,)
            if node.children:
                continuation = LessonController._successful_tree_line(
                    node.children, wanted)
                if continuation:
                    return (node,) + continuation
        return ()

    def reveal(self):
        if self.state not in (QUESTION, FEEDBACK):
            raise LessonStateError("the answer cannot be revealed now")
        question = self.current_step.question
        if question.evaluator == "reviewed_tree":
            if self.state == QUESTION:
                board = self._display_board.clone()
                choices = self._tree_choices
            else:
                board = self.replay.board
                choices = question.tree
            line = self._successful_tree_line(choices, "preferred")
            if not line:
                line = self._successful_tree_line(choices, "acceptable")
            last_move = None
            for node in line:
                last_move, _san = self.adapter.apply_uci(board, node.uci)
            terminal = line[-1]
            self._display_board = board
            self._tree_choices = ()
            self._last_attempt = AttemptResult(
                "revealed", "Solution: " + terminal.feedback,
                line[0].uci, last_move)
            self._step_solved = True
            self._assisted = True
            self.reveals += 1
            self._step_record()["reveals"] += 1
            self._mark_step_solved()
            self.state = FEEDBACK
            return self._last_attempt

        answer = next((item for item in question.answers
                       if item.outcome == "preferred"), None)
        if answer is None:
            answer = next(item for item in question.answers
                          if item.outcome == "acceptable")
        board = self.replay.board
        move, _san = self.adapter.apply_uci(board, answer.uci)
        self._display_board = board
        self._last_attempt = AttemptResult(
            "revealed", "Solution: " + answer.feedback, answer.uci, move)
        self._step_solved = True
        self._assisted = True
        self.reveals += 1
        self._step_record()["reveals"] += 1
        self._mark_step_solved()
        self.state = FEEDBACK
        return self._last_attempt

    def begin_exploration(self, view_state=None):
        if self.state in (EXPLORING, COMPLETED):
            raise LessonStateError("exploration cannot be started now")
        self._exploration_snapshot = _ExplorationSnapshot(
            self.state, self._display_board.clone(), self._last_attempt,
            self._step_solved, self._assisted, view_state,
            tuple(self._tree_choices), self._active_prompt,
            self._active_hints)
        self.state = EXPLORING
        return True

    def explore_uci(self, uci):
        if self.state != EXPLORING:
            raise LessonStateError("not currently exploring")
        try:
            move, _san = self.adapter.apply_uci(self._display_board, uci)
        except MoveResolutionError:
            return AttemptResult("illegal", "That move is not legal here.", uci)
        return AttemptResult(
            "exploring", "Temporary exploration move.", uci, move)

    def return_from_exploration(self):
        if self.state != EXPLORING or self._exploration_snapshot is None:
            raise LessonStateError("there is no exploration state to restore")
        snapshot = self._exploration_snapshot
        self.state = snapshot.state
        self._display_board = snapshot.board
        self._last_attempt = snapshot.last_attempt
        self._step_solved = snapshot.step_solved
        self._assisted = snapshot.assisted
        self._tree_choices = snapshot.tree_choices
        self._active_prompt = snapshot.active_prompt
        self._active_hints = snapshot.active_hints
        self._exploration_snapshot = None
        return snapshot.view_state

    def continue_lesson(self):
        if self.state == READING and not self.current_step.question:
            pass
        elif (self.state != FEEDBACK or not self._step_solved
              or self._last_attempt.outcome == "wrong"):
            raise LessonStateError("the current step is not complete")
        if self.step_index + 1 >= len(self.resolved_steps):
            self.state = COMPLETED
            return False
        self.step_index += 1
        self.state = READING
        self._hint_index = 0
        self._last_attempt = None
        self._step_solved = False
        self._assisted = False
        self._exploration_snapshot = None
        self._load_step_position()
        return True

    def restart(self):
        self.step_index = 0
        self.state = READING
        self._hint_index = 0
        self._last_attempt = None
        self._step_solved = False
        self._assisted = False
        self._exploration_snapshot = None
        self._load_step_position()
