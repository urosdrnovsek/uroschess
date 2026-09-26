"""Original chess tips delivered by the app's fictional animal coaches."""

from dataclasses import dataclass
import random


@dataclass(frozen=True)
class ChessThought:
    name: str
    short_name: str
    quote: str
    portrait: str
    source: str


_COACHES = (
    ("Bruno the Bear", "Bruno", "bruno.bmp", (
        "Bring your pieces into the game early.",
        "Before moving, check what your opponent threatens.",
        "A safe king gives your pieces room to work.",
        "Ask which piece needs a better square.",
        "A pawn in the centre can open new paths.",
        "When you see a check, look one move further.",
        "Your opponent gets a turn too: check their reply.",
        "Try a plan, then see what changed.",
        "Use your pieces together, like a team.",
        "A good move can be quiet and useful.",
        "If a piece is trapped, make it an escape route.",
        "After the game, find one move to learn from.",
    )),
    ("Olive the Owl", "Olive", "olive.bmp", (
        "Look along the whole diagonal before moving.",
        "Find the squares your opponent cannot defend.",
        "A bishop likes a long, open view.",
        "Notice which pawn move helps a piece.",
        "Do not rush a capture; check what follows.",
        "Keep looking for ideas after the opening.",
        "A knight can guard more than one square.",
        "Count the attackers and defenders first.",
        "Make a little space for your next move.",
        "Watch for checks, captures, and threats.",
        "In an endgame, help your king join in.",
        "Pause and look at the whole board.",
    )),
)

THOUGHTS = tuple(
    ChessThought(name, short_name, tip, portrait, "")
    for name, short_name, portrait, tips in _COACHES
    for tip in tips
)


def random_thought(exclude=None):
    """Pick a tip from a different coach when changing an existing card."""
    choices = tuple(
        thought for thought in THOUGHTS
        if exclude is None or thought.portrait != exclude.portrait
    )
    return random.choice(choices or THOUGHTS)
