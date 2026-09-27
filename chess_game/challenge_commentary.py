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
    "tina-turtle": MatchVoice(
        "Oh, a chess game. I suppose my shell can wait.",
        (
            "There. One move closer to my tea break.",
            "Even my pawns look tired today.",
            "I would sigh, but I already did.",
            "Your turn. I'll be here, probably forever.",
            "My shell is heavy; this game feels heavier.",
            "I made a move. How terribly energetic of me.",
            "A quiet moment. At last, something I understand.",
            "My pieces asked for a holiday. I said yes.",
            "Well, the board hasn't run away. Yet.",
            "If patience wins games, I have a chance.",
        ),
        "I won? Oh dear, now they'll expect it again.",
        "You won. At least someone had a lovely day.",
        "A draw. Even the result couldn't make up its mind.",
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
    "tom-rabbit": MatchVoice(
        "Pieces, positions! We have a game to win!",
        (
            "Knight, stop hopping about like it's a picnic!",
            "Bishops, eyes on the board, please!",
            "Pawns, I asked for teamwork, not a parade!",
            "Rooks, stand straight. We have company.",
            "Queen, kindly stop stealing my thunder.",
            "My pieces are testing my patience again.",
            "Did the knights hear a word of my speech?",
            "Everybody focus! Yes, even the king.",
            "No, pawns, the snack break is after the game.",
            "My monocle sees everything. Usually.",
        ),
        "Victory! Pieces, report for a very stern hug.",
        "You won. Pieces, we are having a meeting.",
        "A draw? Pieces, back to training tomorrow!",
    ),
    "olive-owl": MatchVoice(
        "Welcome. Observe carefully, then choose your plan.",
        (
            "The position has changed. Look again.",
            "What is each side trying to achieve?",
            "Consider the reply before you decide.",
            "Which piece needs your attention most?",
            "Compare your options before choosing.",
            "First, ask what your pieces can do.",
            "Look at the whole board, then the details.",
            "What would your opponent like to do?",
            "Take time to picture the next move.",
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
            "You may admire how calm I look.",
            "My brilliance does keep me busy.",
            "Go on. Surprise a future legend.",
            "I even think in style.",
            "A little mystery suits a star like me.",
            "I trust you're taking notes.",
            "My fans must be watching closely.",
            "Take your time. Greatness can wait.",
        ),
        "My legend grows! What an excellent game.",
        "A rematch! My legend requires a second chapter.",
        "A draw? The suspense will delight my fans.",
    ),
}
