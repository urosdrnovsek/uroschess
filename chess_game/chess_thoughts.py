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
        "You spotted a threat? Good work. Find a safe reply.",
        "Take your time, little one. Every move teaches you.",
        "One careful move can make the whole board calmer.",
        "Your king is safer when your pieces stand together.",
        "Try the move in your mind first. You've got this.",
        "If that plan failed, we can build a better one.",
        "Look at your opponent's move. What changed, kiddo?",
        "That pawn can wait. Bring a helper into the game.",
        "A quiet move can bravely protect a friend.",
        "Keep going. Find a better square for one piece.",
    )),
    ("Olivia the Owl", "Olivia", "olive.bmp", (
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
        "A square is easier to use when no pawn guards it.",
        "Help the piece that has nowhere useful to go.",
        "Ask what your opponent wants, then deny the plan.",
        "Wait before a trade that helps their pieces.",
        "Before a trade, look at where the pawns will be.",
        "Extra room helps only if your pieces can use it.",
        "Your king's safety decides which plans are real.",
        "Before pushing a pawn, see what it will open.",
        "One better square can change a quiet position.",
        "Before a check, imagine their reply.",
    )),
    ("Pippa the Pomeranian", "Pippa", "pomeranian.bmp", (
        "Let's bring our sleepy pieces out to play, sweet pea.",
        "Before you move, peek at their little threats.",
        "A cozy king gives your pieces room to shine.",
        "Which piece would love a happier square?",
        "Your pieces make a lovely team when they help.",
        "That pawn can take a tiny step toward the centre.",
        "Let's give your bishop a nice open diagonal.",
        "Can your knight hop somewhere safe and helpful?",
        "Before a capture, look for their reply, darling.",
        "A gentle castle can tuck your king in safely.",
        "One little check may reveal a bigger idea.",
        "Help your rook find an open file, sweetheart.",
        "Help a pawn on its way to the last row, dear.",
        "Even a quiet move can make your position bloom.",
        "Take a breath, dear; the best move will wait.",
    )),
    ("Tina the Turtle", "Tina", "tina.bmp", (
        "I suppose I should check what your move threatens.",
        "My pieces are tired. Perhaps yours need a plan.",
        "A pawn can help, if it feels like moving today.",
        "Count the defenders. I wish it were fewer.",
        "A safe king gives me one less thing to worry about.",
        "Check the whole board. Yes, all of it. Sigh.",
        "Even a slow plan needs a useful next move.",
        "I moved my knight; now it wants a rest.",
        "Before a capture, ask what comes back at you.",
        "My shell is sturdy. Your king needs shelter too.",
        "Look for a loose piece before I lose my patience.",
        "A quiet move might save a noisy problem later.",
        "I would hurry, but checking replies comes first.",
        "That bishop needs space. Don't we all?",
        "One small improvement is enough for today.",
    )),
    ("Chicky", "Chicky", "chicky.bmp", (
        "I think I need to learn how to move a queen.",
        "I'm on my way to become a chessmaster!",
        "Why does a king only move one square?",
        "I meant to move my piece, but I forgot which one.",
        "Is it snack time after this chess move?",
        "My knight can hop! I wish I could hop too.",
        "I am practicing my serious chess face. Beak!",
        "Maybe the pawns are tiny kings in training.",
        "Oops, I was looking at a bug on the board.",
        "One day I will be a chessmaster. First, a nap.",
        "Do rooks get dizzy going only straight?",
        "I tried to castle, but forgot my tiny suitcase.",
        "Is a fork still a fork if I can't eat with it?",
        "My pawn marched forward. I cheered very loudly.",
        "Can I promote into a sandwich instead?",
        "I counted all the squares. Then I lost count.",
        "My serious thinking face looks a bit sleepy.",
        "I waved at the bishop. It slid right past me.",
        "Does the king know we're all protecting him?",
        "Maybe my next move will be legendary. Beak!",
    )),
    ("Monty the Cat", "Monty", "monty.bmp", (
        "How many moves would you last in the game with me?",
        "I once played against a grandmaster!",
        "Own the centre. I like my stage nice and wide.",
        "Check their threats first. Even I do that.",
        "Bring out your pieces. Mine never wait backstage.",
        "Castle early. A legend must keep his king safe.",
        "Count defenders before a capture. I always do.",
        "Look for checks first. I enjoy a grand entrance.",
        "Make a plan, then check their reply. Brilliant, yes?",
        "My knight jumps only where it can stay safe.",
        "In an endgame, my king takes centre stage.",
        "Even my best move needs a second look.",
        "I saw your threat. Naturally, mine is better.",
        "Develop your knight. Mine arrives with applause.",
        "Guard your king. My admirers expect me to.",
        "That pawn break needs timing. I have perfect timing.",
        "Count the defenders. I already counted twice.",
        "An open file is a runway for my rook.",
        "Check their reply first. I hate dull surprises.",
        "Trade only when your position looks as good as mine.",
        "Improve your worst piece. I have no worst piece.",
        "In the endgame, my king deserves the spotlight.",
    )),
    ("Tom the Rabbit", "Tom", "tom.bmp", (
        "Pawns, guard each other! Is that too much to ask?",
        "Knight, find a good square and stay alert!",
        "Bishops, stop staring at your own pawns!",
        "Rooks, use a clear path up the board!",
        "King, get to safety. That's an order!",
        "Queen, check their reply before charging in!",
        "Pieces, work together for once!",
        "A check is loud, but is it useful? Think!",
        "Count the attackers. Count them again!",
        "Don't trade a helper without a reason!",
        "Pawns, no wandering off without a plan!",
        "Look at their threat before you make yours!",
        "My monocle looks for pieces left alone. Do you?",
        "In the endgame, king, you may finally help!",
        "Everybody breathe. Then choose a move!",
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
