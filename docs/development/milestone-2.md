# Milestone 2: one complete guided lesson

Milestone 2 turns the packaged White–Black game into a complete offline
teaching loop. The lesson, **Make your pieces work together**, contains three
reviewed board questions at exact source-game positions.

## Delivered

- Versioned lesson, step, question, reviewed-answer, arrow, and highlight data
  contracts. Lesson prose and attribution live in packaged JSON.
- Deterministic lesson loading. Every UCI node path is resolved against the
  immutable game tree and its exact FEN is checked before the lesson is listed.
- A UI-independent state controller with `READING`, `QUESTION`, `FEEDBACK`,
  `EXPLORING`, and `COMPLETED` states.
- Preferred, acceptable, wrong, illegal, uncovered, and revealed outcomes;
  ordered hints; retry; assisted completion; and hidden prediction overlays.
- Temporary exploration on a cloned board with exact restoration of the source
  cursor, question state, answer state, board, and teaching-panel scroll.
- Semantic board arrows and highlights that use outlines and arrow shapes as
  well as color.
- A wide side-by-side lesson view and a stacked narrow view. Teaching text is
  never hidden and scrolls with the wheel or Page Up/Page Down.
- Versioned SQLite progress in the per-user application-data directory. Resume
  step, attempts, hints, reveals, successful answers, and completion survive
  restarts; progress is never written into the repository.
- A primary **Continue learning** action, guided-library entry, and separate
  access to the complete annotated replay.

## Lesson questions

1. Complete Black's kingside fianchetto. `...Bg7` is preferred, `...d5` is an
   accepted sound alternative, and `...Bh6` receives reviewed retry feedback.
2. Find Black's `17...Be6!!`, keeping the initiative while offering the queen.
3. Find mate in one. Both the historical `41...Rc2#` and `41...Ba3#` are
   accepted, proving the evaluator is not tied to one source continuation.

## Validation

```bash
python -m scripts.validate_content
python -m tests.test_lessons
python -m tests.test_progress
pytest -q
python -m scripts.smoke
```

The tests cover content/FEN diagnostics, state transitions, answer classes,
hint and reveal accounting, exact exploration restoration, both mating moves,
SQLite round trips, semantic annotation rendering, and the narrow lesson UI.

## Deferred

The user-validation gate still requires trying the lesson with beginner and
intermediate learners. More games, opening lessons, endgames, review queues,
and live analysis remain later milestones.
