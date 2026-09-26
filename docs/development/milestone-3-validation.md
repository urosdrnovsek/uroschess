# Milestone 3 release validation

## Automated release checks

Run from the repository root:

```bash
.venv/bin/pytest -q
.venv/bin/python -m scripts.validate_content
.venv/bin/python -m scripts.smoke
```

The content validator must report 18 games, 18 lessons, and 2 courses with no errors. The
test suite covers exact FEN resolution, legal authored branches, preferred and
acceptable terminal answers, assisted completion of every lesson, persistence,
library pagination, keyboard focus, replay scrolling, and wide/narrow lesson
rendering.

For the packaging gate, build a wheel, install it into a temporary directory,
change the working directory outside the checkout, and call
`load_game_library()`. It must return the same 12 entries with no errors.

## Maintainer play-through

For every lesson:

1. Read the objective and confirm the source/credit lines are visible.
2. Use Hint, make the preferred move sequence, and finish the lesson.
3. Restart and confirm progress resumes.
4. Retry a reviewed wrong answer where one is authored.
5. Try an uncovered legal move, make at least one exploration move, and return.
6. Use Show answer and confirm it reaches a successful terminal position.
7. Repeat at Large or Extra large text and once in a narrow window.

Also traverse Home, both Endgames pages, Appearance, replay, and ordinary play
with Tab/Shift+Tab and Enter/Space. Mix keyboard and mouse input; scroll both
lesson text and the complete White–Black move list.

## Human learner gate

This gate requires real learners and must not be marked complete from automated
tests alone. Observe a few beginners and at least one intermediate player using
the lessons without coaching. Record:

- words or chess concepts they cannot explain;
- automatic opponent replies they miss;
- controls they do not discover or understand;
- board arrows, focus rings, or feedback they cannot distinguish;
- whether they can solve a related position and explain why.

Feedback received after the first teaching release: a tester opened Continue
learning and tried to move a piece, but did not discover that the old “Your
turn” button had to be pressed first. Testers also asked for larger lesson
text, simpler sentences for children, a light story in game explanations, and
clear feedback when a legal move differs from the lesson's planned answer.
The lesson now opens ready for a board move. The guided game and the main
instructions across the starter pack have been revised, and unreviewed
legal moves explain how to return and try again. Recheck these changes with
learners; this note is not a completed human validation gate.

Revise the affected lesson's wording or interaction, increment its
`content_revision`, rerun all checks, and keep the observations with the release
notes.
