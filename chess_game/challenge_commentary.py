"""Position-neutral match dialogue, separate from the general chess tips."""

from dataclasses import dataclass


@dataclass(frozen=True)
class MatchVoice:
    greeting: str
    after_move: tuple
    character_wins: str
    character_loses: str
    draw: str


VOICES = {
    "chicky": MatchVoice(
        "Hello! I think I know how the pieces move.",
        (
            "I moved it! That was the important part.",
            "My tiny brain made a very big effort.",
            "Was that clever? I forgot to ask.",
            "Your turn! I shall practise looking wise.",
            "I had a plan. It flew away.",
            "That move used nearly all my feathers.",
            "I hope the pieces know what I am doing.",
            "Thinking is hungry work. Snack later?",
            "I am wearing my serious chess face.",
            "One move closer to becoming a legend. Maybe.",
        ),
        "Oh! Did I win? My feathers are surprised.",
        "I think my crown is still in the egg.",
        "A draw! We both get to keep our crowns.",
    ),
    "pippa-pomeranian": MatchVoice(
        "Hello, sweet pea. Let's enjoy our game.",
        (
            "Your turn, sweet pea. Take a little look.",
            "Let's see your lovely idea, dear.",
            "A tiny pause can help you spot so much.",
            "Look after your pieces, little star.",
            "What would make your position happier?",
            "One careful thought at a time, sweetheart.",
            "I wonder what you'll choose, darling.",
            "Remember to peek at both sides, dear.",
            "Your next idea is ready to bloom.",
            "Take your time; I'm right here.",
        ),
        "What a lovely game. Shall we play again?",
        "You found a wonderful finish, dear. Well played!",
        "A draw. I enjoyed thinking with you, sweet pea.",
    ),
    "bruno-bear": MatchVoice(
        "Let's play a thoughtful game together, kiddo.",
        (
            "Your turn. Take all the time you need.",
            "Let's see what you noticed.",
            "Keep going. You can work this out.",
            "One thoughtful move at a time.",
            "Look around the board before you decide.",
            "You don't have to rush to show courage.",
            "I'm here for a good game with you.",
            "Try your idea. We'll learn from the game.",
            "A fresh look can help when you're unsure.",
            "Take a breath, kiddo. Your turn.",
        ),
        "Good game, kiddo. Every game teaches us.",
        "Well played. I'm proud of your effort.",
        "A draw after a good contest. Nicely done.",
    ),
    "olive-owl": MatchVoice(
        "Welcome. Observe carefully, then choose your plan.",
        (
            "The position has changed. Look again.",
            "What is each side trying to achieve?",
            "Consider the reply before you decide.",
            "Which piece needs your attention most?",
            "Compare your options before choosing.",
            "A plan begins with an honest assessment.",
            "Look at the whole board, then the details.",
            "What would your opponent like to do?",
            "Patience is part of good calculation.",
            "Notice the possibilities, not just the move.",
        ),
        "A decisive game. Look back at its turning points.",
        "You saw the position clearly. Well played.",
        "A balanced result. There is much to learn here.",
    ),
    "monty-cat": MatchVoice(
        "At last, a worthy audience for my chess.",
        (
            "Your turn. Try to make it memorable.",
            "I make this look rather effortless.",
            "You may admire my composure now.",
            "My brilliance does keep me busy.",
            "Go on. Surprise a future legend.",
            "I even think in style.",
            "A little suspense suits a star like me.",
            "I trust you're taking notes.",
            "My fans would be on the edge of their seats.",
            "Take your time. Greatness can wait.",
        ),
        "My legend grows! What an excellent game.",
        "A rematch! My legend requires a second chapter.",
        "A draw? The suspense will delight my fans.",
    ),
}
