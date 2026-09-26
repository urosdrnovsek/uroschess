# Milestone 3 — Small teaching release

Status: engineering complete; external learner-validation gate remains

Milestone 3 is being delivered as small, independently reviewable slices after
the completed guided-game foundation.

## Slice 1 — Shared controls and visible keyboard focus

Implemented:

- Moved the reusable `Button` description into `chess_game.views.widgets`.
- Added Tab and Shift+Tab traversal for visible menu and panel controls.
- Added Enter and Space activation for the focused control.
- Added a high-contrast focus ring to menu, play, replay, lesson, and promotion
  controls.
- Kept board-square keyboard movement unchanged when no button has focus.
- Added headless checks for focus traversal, activation, and visible rendering.

Manual validation still required:

- Traverse every screen with Tab and Shift+Tab at wide and narrow sizes.
- Confirm the focus ring remains easy to see with each Omarchy palette.
- Check mixed mouse and keyboard use, including promotion choices.

## Slice 2 — Text sizing and persisted preferences

Implemented:

- Added Standard, Large, and Extra large text choices to Appearance.
- Rebuilds menu, status, study, move-list, and coordinate fonts immediately.
- Persists text size, board style, piece colours, play difficulty, and replay
  speed in the existing per-user SQLite database.
- Adds a persisted sound on/off control that remains usable even when the
  machine has no available mixer device.
- Migrates progress schema 1 or 2 transactionally to schema 3 without losing
  lesson history.
- Ignores unsupported saved values and falls back to safe defaults.
- Added tests for both migration paths, setting round-trips, font resizing, and
  restoring preferences after an application restart.

Manual validation still required:

- Read the complete lesson at all three text sizes in wide and narrow layouts.
- Check long labels and lesson titles for clipping.
- Confirm persisted choices on a real application restart.

## Slice 3 — Controlled replay move-list scrolling

Implemented:

- Added a stable first-visible-move cursor for the replay move list.
- Added mouse-wheel scrolling in three-row steps.
- Added Page Up and Page Down scrolling by one visible page.
- Added a proportional scrollbar to long move lists.
- Pauses autoplay when the learner scrolls manually.
- Returns to automatic current-move tracking after Previous, Next, First,
  Last, autoplay, or clicking a move.
- Added headless checks for direct scrolling, page navigation, click-to-jump,
  and keeping the last move visible.

Manual validation still required:

- Scroll the complete White–Black move list at multiple window heights.
- Mix scrolling, autoplay, arrow navigation, and click-to-jump.
- Confirm the scrollbar remains visible with light and dark palettes.

## Slice 4 — Versioned multi-move exercise contracts

Implemented:

- Added lesson schema version 2 while retaining schema version 1 support.
- Added a finite `reviewed_tree` contract with explicit learner and opponent
  roles, continuing moves, terminal outcomes, and authored feedback.
- Validates every branch move against its exact preceding position.
- Applies the first ordered opponent reply automatically and validates every
  authored alternative branch.
- Keeps an exercise incomplete until a preferred or acceptable terminal move.
- Restores the exact tree cursor and board after temporary exploration.
- Supports retry and deterministic assisted reveal from both the initial and an
  intermediate exercise position.
- Added parser, structural, legality, controller, and headless UI checks.

The full contract and authoring example are documented in
`docs/development/multi-move-exercises.md`.

Manual validation still required:

- Play the bundled schema-v2 exercises with beginner learners.
- Check that automatic opponent replies are noticed and understood.
- Review intermediate feedback, hints, retry, reveal, and exploration wording.

## Slice 5 — Categorized starter lesson batch

Implemented:

- Added separate Guided games, Openings, and Endgames entry points on Home.
- Added category-aware library headings, filtering, cards, and empty states.
- Added paged library navigation so every lesson remains reachable by mouse,
  wheel, and keyboard as the collection grows.
- Kept historical games distinct from explicitly labelled synthetic training
  positions and lines.
- Added five beginner opening lessons: opening essentials, Italian Game
  development, the Queen's Gambit plan, Black against 1.e4, and Black against
  1.d4.
- Added six beginner endgames: checkmate versus stalemate, promotion, queen
  mate, rook mate, the square of the pawn, and king activity/opposition.
- Verified Qb7# versus Qb6 stalemate, queen- and rook-mate terminal positions,
  all promotion choices, and a complete pawn-catching continuation.
- Displays concise source names and licenses in lesson content while retaining
  full attribution metadata in the validated package.
- Added category routing, content semantics, complete assisted play-through,
  and progress-independent loading tests.

The starter pack now contains twelve lessons: one guided tournament game, five
opening lessons, and six beginner endgames. All content is bundled package data
and works without a network connection or separately installed chess engine.

Manual validation still required:

- Try all three new lessons with beginners before expanding the collection.
- Check whether learners notice the automatic reply in multi-move exercises.
- Revise any unclear explanation or misleading accepted/wrong classification.
- Recheck card readability and navigation at large text sizes.

## Release verification

- Deterministic validation checks every PGN, exact lesson position, reviewed
  branch, objective, source name, license, and attribution.
- Automated controller play-throughs cover all lessons, including multi-move
  automatic replies, retry, reveal, and temporary exploration.
- A built wheel is installed into an isolated target outside the checkout and
  its complete starter pack is loaded through package resources.
- Headless rendering covers Home, both library pages, replay, lesson question,
  wide and narrow lesson layouts, and all three text sizes.

The remaining gate cannot be completed by automation: put the lessons in front
of beginner and intermediate learners, record unclear wording or controls, and
revise from that evidence. Automated completion is evidence of correctness, not
proof that the material teaches well. The concrete checklist is in
`docs/development/milestone-3-validation.md`.

The review queue, live analysis, mass content imports, and speculative services
remain outside this milestone.
