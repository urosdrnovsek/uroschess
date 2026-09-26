"""Choose authored, position-aware advice for a fixed lesson player."""

from ..chess_thoughts import ChessThought
from .lessons import COMPLETED, EXPLORING


def coach_advice(lesson, transient_message=""):
    if lesson.state == EXPLORING:
        return "Try your idea, then return to this lesson."
    if transient_message:
        return transient_message
    if lesson.state == COMPLETED:
        return lesson.lesson.takeaway
    if lesson.last_attempt:
        return lesson.last_attempt.feedback
    return lesson.current_step.coach_prompt or lesson.lesson.objective


def coach_thought(player, lesson, transient_message=""):
    advice = coach_advice(lesson, transient_message)
    # The complete advice remains in the lesson panel. Keep the portrait card
    # short enough to work beside the board and in the compact strip.
    if len(advice) > 85:
        advice = advice[:82].rsplit(" ", 1)[0] + "…"
    return ChessThought(
        player.name, player.short_name, advice, player.portrait, "")
