"""Lesson screen actions; rendering and app navigation remain in ChessUI."""

from . import sound
from .moves import game_status
from .menu import GUIDE_LESSONS
from .study import (EXPLORING, QUESTION, READING, LessonController,
                    ProgressStore, ProgressStoreError)
from .study.coaching import (BEGINNER_COACH_IDS, BEGINNER_RETRY_MESSAGE,
                             coach_advice)


class LessonActionsMixin:
    def start_lesson(self, entry, course_id=None):
        self.toast = ""
        self._cancel_challenge_search()
        if self.game_library:
            locked_course = next((course for course in self.game_library.courses
                                  if course.entitlement_id and
                                  entry.lesson.lesson_id in course.lesson_ids and
                                  not self._course_unlocked(course)), None)
            if locked_course is not None:
                self._flash("Beat Monty once in Character Challenge to unlock his lesson.")
                return
        self._reset_button_focus()
        return_view = self.menu_view if self.scene == "menu" else self.lesson_return_view
        self.scene = "lesson"
        self.lesson_entry = entry
        self.lesson_course_id = course_id
        self.lesson_return_view = (
            "course" if self.lesson_course_id else
            return_view if return_view in ("opening_hub", "library",
                                           "guide_lessons")
            else "library")
        self.coach_profile = (self.game_library.player(
            entry.lesson.coach_player_id) if entry.lesson.coach_player_id
            and self.game_library else None)
        if self.coach_profile is None and self.game_library:
            guide_id = next((ident for ident, lesson_ids in GUIDE_LESSONS.items()
                             if entry.lesson.lesson_id in lesson_ids), None)
            if guide_id:
                self.coach_profile = self.game_library.player(guide_id)
        self.replay_autoplay = False
        self.thinking = False
        self.flipped = False
        self.lesson_scroll = 0
        self.lesson_message = ""
        self.lesson_message_kind = "hint"
        self.lesson_retry_feedback = ""
        record = None
        step_records = {}
        if self.progress_store is None and not self.progress_error:
            try:
                self.progress_store = ProgressStore()
            except ProgressStoreError as error:
                self.progress_error = str(error)
        if self.progress_store is not None:
            try:
                record = self.progress_store.load(entry.lesson.lesson_id)
                step_records = self.progress_store.load_step_progress(
                    entry.lesson.lesson_id, entry.lesson.content_revision)
            except Exception as error:
                self.progress_error = str(error)
        same_revision = bool(
            record and record.content_revision == entry.lesson.content_revision)
        totals = ({
            "attempts": record.attempts,
            "hints_used": record.hints_used,
            "reveals": record.reveals,
            "successes": record.successes,
        } if record else None)
        self.lesson = LessonController(
            entry.game, entry.lesson,
            resume_step=record.step_index if same_revision else 0,
            progress_totals=totals,
            completed=bool(same_revision and record.completed),
            step_progress=step_records,
            resume_assisted=bool(same_revision and record.active_assisted),
        )
        if self.lesson.state == READING and self.lesson.current_step.question:
            self.lesson.begin_question()
        if self.progress_error:
            self.lesson_message = "Progress is unavailable: " + self.progress_error
        self._layout()
        self._ensure_fonts()
        self._game_bg = None
        self._sync_lesson_position()
        self._save_lesson_progress()
        if self.coach_profile is None:
            self._change_chess_thought(play_sound=False)
        else:
            self._thought_previous = None
        if self.lesson_course_id:
            self._save_preferences(last_course_id=self.lesson_course_id)

    def _course_id_for_lesson(self, lesson_id):
        if self.game_library:
            candidates = [course.course_id for course in self.game_library.courses
                          if course.published and lesson_id in course.lesson_ids]
            if self.active_course_id in candidates:
                return self.active_course_id
            if len(candidates) == 1:
                return candidates[0]
        return None

    def _repeat_coach_advice(self):
        if self.coach_profile is None or self.lesson is None:
            return
        self.lesson_message = coach_advice(self.lesson, self.lesson_message)
        self._show_latest_lesson_message()
        sound.play("click")
        self._dirty = True

    def _sync_lesson_position(self, last_move=None):
        self.board = self.lesson.board
        self.moves = []
        self.sans = []
        self.last_move = (last_move if last_move is not None
                          else self.lesson.replay.current_move)
        self.selected = None
        self.legal_from_selected = []
        self.pending_promo = None
        self.cursor = None
        self.dragging = None
        self.drag_started = False
        self.status = game_status(self.board)
        self._dirty = True

    def _save_lesson_progress(self):
        if self.progress_store is None or self.lesson is None:
            return
        try:
            self.progress_store.save(self.lesson)
            self._course_summary_cache.clear()
        except Exception as error:
            self.progress_error = str(error)
            self.lesson_message = "Progress could not be saved: " + str(error)

    def _lesson_start_question(self):
        if self.lesson.state == READING:
            self.lesson.begin_question()
        self.lesson_message = ""
        self._sync_lesson_position()
        self._save_lesson_progress()

    def _show_latest_lesson_message(self):
        # The panel clamps this to its new content height on the next draw.
        self.lesson_scroll = 1_000_000

    def _lesson_hint(self):
        self.lesson_message = self.lesson.request_hint()
        self.lesson_message_kind = "hint"
        self._show_latest_lesson_message()
        self._save_lesson_progress()
        self._dirty = True

    def _lesson_reveal(self):
        result = self.lesson.reveal()
        self.lesson_message = ""
        self._show_latest_lesson_message()
        self._sync_lesson_position(result.move)
        self._save_lesson_progress()

    def _lesson_retry(self):
        self.lesson.retry()
        self.lesson_message = ""
        self.lesson_scroll = 0
        self._sync_lesson_position()

    def _lesson_continue(self):
        self.lesson.continue_lesson()
        if self.lesson.state == READING and self.lesson.current_step.question:
            self.lesson.begin_question()
        self.lesson_scroll = 0
        self.lesson_message = ""
        self._sync_lesson_position()
        self._save_lesson_progress()

    def _lesson_begin_exploration(self):
        self.lesson.begin_exploration({"scroll": self.lesson_scroll})
        self.lesson_message = "Try any move you are curious about."
        self._sync_lesson_position()

    def _lesson_return(self):
        view_state = self.lesson.return_from_exploration()
        if isinstance(view_state, dict):
            self.lesson_scroll = int(view_state.get("scroll", 0))
        self.lesson_message = ""
        self._sync_lesson_position()

    def _lesson_restart(self):
        self.lesson.restart()
        if self.lesson.current_step.question:
            self.lesson.begin_question()
        self.lesson_scroll = 0
        self.lesson_message = ""
        self._sync_lesson_position()
        self._save_lesson_progress()

    def _next_path_entry(self):
        if self.lesson_course_id and self.game_library:
            course = self.game_library.course(self.lesson_course_id)
            if course:
                ids = course.lesson_ids
                lesson_id = self.lesson_entry.lesson.lesson_id
                if lesson_id in ids and ids.index(lesson_id) + 1 < len(ids):
                    return self.game_library.lesson_entry(
                        ids[ids.index(lesson_id) + 1])
            return None
        if self.lesson_return_view == "guide_lessons":
            return None
        entries = self._path_entries()
        for index, entry in enumerate(entries[:-1]):
            if self.lesson_entry and entry.lesson.lesson_id == self.lesson_entry.lesson.lesson_id:
                return entries[index + 1]
        return None

    def _lesson_neighbor(self, delta):
        if not self.game_library or self.lesson_entry is None:
            return None
        lesson_id = self.lesson_entry.lesson.lesson_id
        guide_id = self.lesson_entry.lesson.coach_player_id or next(
            (ident for ident, lesson_ids in GUIDE_LESSONS.items()
             if lesson_id in lesson_ids), None)
        if guide_id is None:
            entries = tuple((entry, self._course_id_for_lesson(
                entry.lesson.lesson_id)) for entry in self._path_entries())
        else:
            entries = []
            for item in self._guide_entries(guide_id):
                if hasattr(item, "course_id"):
                    entries.extend((self.game_library.lesson_entry(item_id),
                                    item.course_id) for item_id in item.lesson_ids)
                else:
                    entries.append((item, None))
        current = next((index for index, (entry, course_id) in
                        enumerate(entries) if entry is not None and
                        entry.lesson.lesson_id == lesson_id and
                        course_id == self.lesson_course_id), None)
        if current is None:
            current = next((index for index, (entry, _) in enumerate(entries)
                            if entry is not None and
                            entry.lesson.lesson_id == lesson_id), None)
        if current is None or not 0 <= current + delta < len(entries):
            return None
        entry, course_id = entries[current + delta]
        return (entry, course_id, guide_id) if entry is not None else None

    def _lesson_switch(self, delta):
        neighbor = self._lesson_neighbor(delta)
        if neighbor is None:
            return
        entry, course_id, guide_id = neighbor
        self._save_lesson_progress()
        if guide_id is not None:
            self.active_guide_id = guide_id
            guide_items = self._guide_entries(guide_id)
            guide_index = None
            for index, item in enumerate(guide_items):
                if course_id and getattr(item, "course_id", None) == course_id:
                    guide_index = index
                    break
                if (not course_id and not hasattr(item, "course_id") and
                        item.lesson.lesson_id == entry.lesson.lesson_id):
                    guide_index = index
                    break
            if guide_index is not None:
                per_page = 2 if min(430, self.win_h - 70) < 320 else 3
                self.guide_lesson_page = guide_index // per_page
        if course_id:
            if course_id != self.active_course_id:
                self.course_return_view = "guide_lessons"
            self.active_course_id = course_id
            course = self.game_library.course(course_id)
            if course:
                per_page = 2 if len(course.lesson_ids) > 3 else 3
                self.course_lesson_page = (
                    course.lesson_ids.index(entry.lesson.lesson_id) // per_page)
        self.start_lesson(entry, course_id=course_id)
        self.lesson_return_view = "course" if course_id else "guide_lessons"

    def _lesson_previous(self):
        self._lesson_switch(-1)

    def _lesson_next(self):
        self._lesson_switch(1)

    def _apply_lesson_move(self, move):
        uci = str(move)
        if self.lesson.state == QUESTION:
            result = self.lesson.attempt_uci(
                uci, view_state={"scroll": self.lesson_scroll})
        elif self.lesson.state == EXPLORING:
            result = self.lesson.explore_uci(uci)
        else:
            return False
        beginner_coach = self.lesson.lesson.coach_player_id in BEGINNER_COACH_IDS
        if beginner_coach and result.outcome in ("wrong", "off_goal", "not_covered"):
            if result.outcome in ("wrong", "off_goal"):
                self.lesson.retry()
            self.lesson_message = BEGINNER_RETRY_MESSAGE
            self.lesson_message_kind = ("try_again" if result.outcome == "wrong"
                                        else "legal_move")
            self.lesson_retry_feedback = result.feedback
        else:
            self.lesson_message = (result.feedback
                                   if result.outcome == "not_covered" else "")
            self.lesson_message_kind = "hint"
            self.lesson_retry_feedback = ""
        if self.lesson_message_kind in ("try_again", "legal_move"):
            self._show_latest_lesson_message()
        elif result.outcome != "illegal":
            self._show_latest_lesson_message()
        last_move = (None if result.outcome in ("wrong", "off_goal", "not_covered")
                     else result.move)
        self._sync_lesson_position(last_move)
        self._save_lesson_progress()
        return result.outcome != "illegal"

