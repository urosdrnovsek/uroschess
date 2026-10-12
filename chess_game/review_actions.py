"""Finished challenge review navigation and related lesson actions."""

from .study.match_review import review_match


class ReviewActionsMixin:
    def _review_challenge(self):
        try:
            review = review_match(self.challenge)
        except ValueError as error:
            self._flash(str(error))
            return
        self.start_replay(review.entry, return_to={
            'scene': 'menu', 'view': 'challenge_result'})
        self.match_review = review
        if review.moments:
            self.replay.jump((0,) * review.moments[0].ply)
            self._sync_replay_position()

    def _next_review_moment(self):
        plies = [moment.ply for moment in self.match_review.moments]
        target = next((ply for ply in plies if ply > self.replay.ply),
                      plies[0] if plies else 0)
        self.replay.jump((0,) * target)
        self._sync_replay_position()
        self._dirty = True

    def _practise_review(self):
        ident = self.match_review.practice_id
        entry = self.game_library.lesson_entry(ident) if self.game_library else None
        if entry is None:
            self._flash('This practice lesson is unavailable.')
            return
        self._to_menu()
        self.start_lesson(entry, course_id=self._course_id_for_lesson(ident))
