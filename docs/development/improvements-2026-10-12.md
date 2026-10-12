# Review improvements — 12 October 2026

Implemented the six review priorities where work can be done in the repository:

- Engine quiescence checks terminal states and searches all legal check evasions;
  captures include en passant. Search restores the board when timeouts,
  cancellation, or errors unwind a branch. Mate takes precedence over the
  move-count draw. Tests exercise forced interruption inside a branch.
- Audited all authored alternatives. `off_goal` describes legal moves that miss
  the requested task, while `wrong` retains concrete tactical or goal failures.
  Both retain the question board. The UI gives legal alternatives a distinct
  label and preserves honest helped/independent progress.
- Added two independent exercises in unfamiliar positions: a knight capture
  with Chicky and several acceptable rook moves onto open files with Bruno.
  They are reachable through their guides' practice lessons. Existing courses,
  step identities, and compatible progress stay intact. The pack now has
  33 games and 33 lessons, with nine courses.
- Added Start with Chicky / Continue learning on the home screen, proportional
  reading fonts with monospace move notation, flatter Theme board squares,
  and authored source cues instead of highlighting every movable piece.
  Feedback labels and answer-only fork/bishop overlays make consequences clearer.
- Finished challenge reviews replay verified histories with up to two factual
  moments and a related practice route. See ADR 0004.
- Extracted lesson and engine actions from ChessUI; both computer-play modes
  share cancellation and worker handling. CI now explicitly validates content,
  builds a wheel, and checks installation outside the checkout. The desktop
  launcher uses Uroschess branding and describes learning features. Immutable
  bundled game parsing is cached by full content and provenance; modified
  resources are reread and validated rather than hidden by filename caching.

Real learner observation remains **pending**. The review guide now contains a
five-session procedure and an anonymous results template. No observed teaching
benefit or calibrated player rating is claimed.

Calibration uses the actual opponent policies, both colour assignments, seed
11, and a 160-ply cap across all six adjacent pairs. The endgame run completed
12 games, all draws, without search failures or truncations. This simple pawn
ending does not distinguish opponent strength. A separate start-position run
is recorded alongside it: nine stronger-side wins, one loss and two games
stopped at the cap, with zero search failures. Monty and Olivia split their
start-position games. Across both reports, 24 games produced nine wins, one
loss, twelve draws, two truncations and zero search failures. Small samples
and wall-clock search still limit any strength conclusion. Policies have not
been tuned from insufficient evidence.

Reports: [pawn endings](calibration-2026-10-12.json) and
[start positions](calibration-start-2026-10-12.json).

## Verification

- Full suite: 175 passed, with one old navigation assertion still treating
  Bruno's previous last lesson as the end of his path. Updated it to navigate
  into the new transfer lesson, check the disabled final arrow, and return to
  that lesson's guide page; the focused rerun passed. All 176 tests are verified
  across the full run and that rerun. Engine/review checks also passed separately.
- Content validation passed for all 33 games and 33 lessons.
- Rendering smoke passed. README screenshots were regenerated and representative
  home, lesson, narrow beginner, and feedback screens were inspected.
- Home, result and review controls fit at 360×320, 420×720 and 980×760 with
  Standard, Large and Extra large text. Legal feedback keeps its label visible
  while scrolling; scene transitions clear obsolete toasts.
- Built a wheel and tested its installed package outside the checkout without
  downloading runtime dependencies. Content, home, lesson, replay, challenge
  resume and all seven packaged BMP portraits passed.
- Shell syntax, Python compilation and `git diff --check` passed.

Checks used Python 3.14.7 and Pygame 2.6.1 on Linux. The existing Pygame AVX2
build warning remains. The CI matrix is configured for 3.9, 3.12 and 3.13;
those interpreters and other desktop platforms were not tested locally.
Real learner observation and a larger opponent-strength sample remain pending.
