# Finished match review

The result screen offers a review after a challenge ends. Review reconstructs
all moves from the initial position, rejects illegal histories, compares the
final FEN with the retained match board, and verifies the terminal result.
Resignation is treated as a match decision rather than a board outcome.

The first version annotates only facts that follow from the rules: the learner
answered check, castled, promoted, or the match ended in mate or stalemate.
It retains at most two moments, one early and one final, and links the final
moment to an existing practice lesson. A match without such events still has
replay and a king safety practice route. The review never claims an engine
choice was best or that castling made this particular position objectively safe.

The recorded review tree and playback boards are separate from the challenge
session. Returning restores the terminal display board and result; review does
not update match moves, rewards, or progress. Opening practice leaves the
finished challenge and uses ordinary lesson progress. Invalid evidence is
reported instead of becoming coaching. No live match has a review entry point.

`study/match_review.py` implements verification and facts independently of
Pygame. `review_actions.py` connects replay, result navigation, and practice.
`lesson_actions.py` and `engine_actions.py` hold the existing lesson screen
actions and shared cancellable computer-move lifecycle outside `ChessUI`.
