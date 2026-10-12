"""Cancellable computer-move lifecycle shared by ordinary and challenge play."""

import queue
import threading
import time
from . import ai
from .difficulty import DIFFICULTIES
from .notation import to_fen
from .pieces import WHITE, BLACK


class EngineActionsMixin:
    def _ai_params(self):
        _, tl, dcap = DIFFICULTIES[self.difficulty]
        return tl, dcap

    def _maybe_start_ai(self):
        if self.challenge_save_error is not None:
            return
        if self.status != "ongoing":
            return
        if self.board.side_to_move in self.human_colors:
            return
        if self.thinking:
            return
        if self.challenge is not None:
            self.thinking = True
            self.think_started = time.monotonic()
            session = self.challenge
            token = (session.match_id, self.challenge_generation,
                     len(session.moves), to_fen(session.board))
            result_queue = self.ai_queue
            if session.opponent.preset is None:
                try:
                    result_queue.put((session.choose_move(), 0, None, token))
                except Exception as error:
                    result_queue.put((None, None, str(error), token))
            else:
                random_move = session.choose_random_search_move()
                if random_move is not None:
                    result_queue.put((random_move, 0, None, token))
                    return
                cancel = threading.Event()
                self.challenge_cancel_event = cancel
                snap = session.board.clone()
                params = session.opponent.policy_parameters

                self._launch_search(snap, params["seconds"], params["depth"],
                                    cancel, result_queue, token)
            return
        self.thinking = True
        self.think_started = time.monotonic()
        tl, dcap = self._ai_params()
        snap = self.board.clone()
        result_queue = self.ai_queue

        cancel = threading.Event()
        self.challenge_cancel_event = cancel
        self._launch_search(snap, tl, dcap, cancel, result_queue)

    def _poll_ai(self):
        if not self.thinking:
            return False
        try:
            response = self.ai_queue.get_nowait()
        except queue.Empty:
            return False
        if self.challenge is not None:
            move, score, error, token = response
            session = self.challenge
            expected = (session.match_id, self.challenge_generation,
                        len(session.moves), to_fen(session.board))
            if (token != expected or session.status != "ongoing" or
                    session.board.side_to_move == session.color):
                return False
        else:
            move, score, error = response
        self.thinking = False
        self.challenge_cancel_event = None
        if error is not None:
            if self.challenge is not None:
                self.challenge_ai_error = True
            self._flash("AI move failed: " + error)
            self._dirty = True
            return True
        if self.challenge is not None:
            self.challenge_ai_error = False
        self.eval_cp = score if self.board.side_to_move == WHITE else -score
        if self.challenge is not None:
            if move is None:
                self.challenge_ai_error = True
                self._flash("Opponent did not return a move")
                return True
            try:
                if session.opponent.preset is not None:
                    session.authorize_search_move(move)
            except ValueError as error:
                self.challenge_ai_error = True
                self._flash("Opponent move failed: " + str(error))
                return True
            self._apply(move, actor=BLACK if session.color == WHITE else WHITE)
        elif move is not None:
            self._apply(move)
        return True

    @staticmethod
    def _launch_search(board, seconds, depth, cancel, result_queue, token=None):
        def work():
            try:
                move, score, _pv, _nodes = ai.analyse(
                    board, time_limit=seconds, max_depth=depth,
                    cancel_event=cancel)
                response = (move, score, None)
            except ai.SearchCancelled:
                return
            except Exception as error:
                response = (None, None, str(error))
            if not cancel.is_set():
                result_queue.put(response + (token,) if token is not None else response)
        threading.Thread(target=work, daemon=True).start()

