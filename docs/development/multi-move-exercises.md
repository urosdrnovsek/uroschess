# Multi-move reviewed exercises

Lesson schema version 2 adds the `reviewed_tree` question evaluator. It models a
finite, human-reviewed sequence without requiring an engine at lesson runtime.
Schema version 1 and its `reviewed_moves` evaluator remain supported.

## Contract

A reviewed tree starts with one or more learner nodes. A learner node has:

- `uci`: the move from the current position;
- `role`: `learner`;
- `outcome`: `continue`, `preferred`, `acceptable`, or `wrong`;
- `feedback`: required learner-facing text;
- `children`: required only for `continue`.

A continuing learner move has one or more ordered opponent children. The first
is the deterministic runtime reply; later children are checked alternative
branches. An opponent node uses `role: opponent` and `outcome: reply`, and
contains one or more next learner choices. Every continuing branch must
eventually reach a `preferred` or `acceptable` terminal learner move.

```json
{
  "schema_version": 2,
  "question": {
    "kind": "move",
    "timing": "before_move",
    "evaluator": "reviewed_tree",
    "prompt": "Develop the bishop, then make the king safe.",
    "tree": [
      {
        "uci": "f8g7",
        "role": "learner",
        "outcome": "continue",
        "feedback": "Good. The bishop is active.",
        "children": [
          {
            "uci": "d2d4",
            "role": "opponent",
            "outcome": "reply",
            "feedback": "White builds the centre.",
            "children": [
              {
                "uci": "e8g8",
                "role": "learner",
                "outcome": "preferred",
                "feedback": "Well done. Black developed and castled."
              }
            ]
          }
        ]
      }
    ]
  }
}
```

## Validation and runtime behavior

- Every move in every branch is resolved against the exact preceding position.
- Illegal moves reject the lesson with its game, lesson, step, and branch.
- Sibling moves must be unique and roles must alternate.
- A terminal move cannot contain children.
- The first authored opponent reply is applied automatically after `continue`;
  every ordered alternative is still validated.
- The step completes only at a preferred or acceptable terminal learner move.
- An uncovered legal move enters temporary exploration; returning restores the
  exact board and reviewed-tree cursor.
- Retry resets the exercise to its authored starting position.
- Show answer follows a deterministic preferred line, falling back to an
  acceptable line, and records assisted completion.

The current starter lesson remains schema version 1. A schema-v2 exercise
should only be bundled after its complete tree and teaching text are reviewed.
