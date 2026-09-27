"""Portrait roster and tip rotation checks."""

from collections import Counter
from importlib import resources

from chess_game.chess_thoughts import THOUGHTS, random_thought


def test_each_fictional_coach_has_original_tips_and_a_portrait():
    counts = Counter(thought.portrait for thought in THOUGHTS)
    assert counts == {"bruno.bmp": 22, "olive.bmp": 22,
                      "pomeranian.bmp": 15, "chicky.bmp": 20,
                      "monty.bmp": 22, "tina.bmp": 15, "tom.bmp": 15}
    assert len(THOUGHTS) == len({thought.quote for thought in THOUGHTS})
    for thought in THOUGHTS:
        assert thought.source == ""
        assert len(thought.quote) <= 56
        assert resources.is_resource("chess_game.assets.portraits",
                                     thought.portrait)


def test_rotation_changes_the_player_not_only_the_tip():
    for current in THOUGHTS:
        for _ in range(20):
            assert random_thought(exclude=current).portrait != current.portrait
