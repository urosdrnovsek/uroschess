"""Short encouragement for the fictional coach card during lessons."""

from ..chess_thoughts import ChessThought
from .lessons import COMPLETED, EXPLORING, FEEDBACK


BEGINNER_RETRY_MESSAGE = "Hmm, let's try again!"
BEGINNER_COACH_IDS = ("chicky", "pippa-pomeranian", "tina-turtle")


def coach_advice(lesson, transient_message=""):
    if (lesson.lesson.coach_player_id in BEGINNER_COACH_IDS
            and transient_message == BEGINNER_RETRY_MESSAGE):
        return BEGINNER_RETRY_MESSAGE
    if lesson.state == EXPLORING:
        return "You can try a different move here."
    if lesson.state == COMPLETED:
        return "Nice work. You can try another lesson."
    if lesson.state == FEEDBACK:
        return "See what your move changed."
    return "Take your time and look at the board."


def coach_thought(player, lesson, transient_message=""):
    advice = coach_advice(lesson, transient_message)
    # Keep this separate from the question, hint, and feedback in the panel.
    if len(advice) > 85:
        advice = advice[:82].rsplit(" ", 1)[0] + "…"
    return ChessThought(
        player.name, player.short_name, advice, player.portrait, "")
