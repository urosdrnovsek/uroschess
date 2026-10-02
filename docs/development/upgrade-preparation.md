# Next upgrade: character teaching paths

Prepared from `Instructions/New update blueprint.txt` (28 September 2026),
`Instructions/Blueprint_Handbook.md`, and the 29 September checkout. Milestones
A and B were already implemented. The first milestone-C slice now adds a
general course model, seven Chicky lessons, and Pippa's and Tina's first lessons; the rest
of the character paths remain planned.

## Baseline and ownership

- Before this slice, the starter pack had 18 lessons and two published opening
  courses. It now has 27 lessons and five published courses. Existing
  course IDs are `bruno-scotch-first-ideas` and
  `olive-catalan-first-ideas`; preserve them and all lesson IDs and revisions.
- `chess_game/study/content.py` now loads both schema-1 opening courses and
  schema-2 general courses. Historical source requirements remain specific to
  historical courses. `GameLibrary.courses_for_category` filters all supported
  categories.
- `chess_game/menu.py` now pages longer course lesson lists. `chess_game/ui.py`
  carries an originating course through course lessons and return routes;
  ambiguous Continue matches use the active course when available.
- `chess_game/study/course_progress.py` derives completion from revisioned
  lesson progress. Reuse it; do not add a second progress store for courses.
  `chess_game/study/lessons.py` owns lesson interaction and
  `chess_game/study/progress.py` owns SQLite migrations (currently schema 10).
- Starter content uses JSON lessons, PGN positions, and BMP portraits. Keep
  original material labelled as original; require real provenance for any
  historical game. Keep runtime dependencies MIT compatible.

## Existing lesson inventory

"Assumed" condenses each lesson's `prerequisites` field. A role is a planning
fit, not permission to change its coach or reuse its ID for different content.
"Revise" means retain the stable ID and increment `content_revision` if its
instructional meaning changes. The two existing coach courses remain intact.

| Lesson ID | Current concept and assumed knowledge | Candidate role | Decision |
| --- | --- | --- | --- |
| `opening-essentials` | Centre, development, king safety; legal moves | Pippa foundations | Reuse after Chicky basics |
| `italian-development` | Development and central break; opening basics, castling | Tom replies or Pippa follow-up | Revise only after checking authored branches and coach attribution |
| `queens-gambit-plan` | Centre and development; opening basics | Pippa follow-up | Reuse as an optional opening application |
| `black-against-e4` | Reply in centre and develop; opening basics | Tom unfamiliar reply | Reused in Tom's course at revision 3 |
| `black-against-d4` | Centre and pawn tension; opening basics | Tom unfamiliar reply | Revise for a concrete threat lesson if needed |
| `mate-or-stalemate` | Mate versus stalemate; check, mate, queen moves | Tina finish | Reused in Tina's course at revision 3 |
| `promote-the-pawn` | Promotion; pawn movement and promotion | Tina promotion | Revise prompt/scaffold for first endgame path |
| `queen-and-king-mate` | King and queen coordination; mate/stalemate, queen moves | Tina follow-up | Reuse |
| `rook-and-king-mate` | King and rook coordination; mate/stalemate, rook moves | Tina follow-up | Reuse |
| `square-of-the-pawn` | Pawn race; king movement, promotion | Tina follow-up | Reuse after simpler king activity |
| `opposition-and-king-activity` | Opposition and passed pawn; king movement, passed pawns | Tina or Bruno advanced endgame | Reuse later, not in first path |
| `coordination-before-material` | Coordination and calculation; legal moves, mate, piece values | Olivia tactics or Bruno planning | Revise attribution/branch wording before sharing |
| `bruno-scotch-make-room` | Central pawn break; legal moves, opening basics | Existing Bruno course | Keep course and lesson ID |
| `bruno-scotch-active-knight` | Recapture and knight activity; preceding Bruno lesson | Existing Bruno course | Keep course and lesson ID |
| `bruno-scotch-try-alone` | Independent central plan; preceding Bruno lesson | Existing Bruno course | Keep course and lesson ID |
| `olive-catalan-bishop` | Bishop development; legal moves, opening basics | Existing Olivia course (`olive-owl`) | Keep course and lesson ID |
| `olive-catalan-king-safety` | Castling and safety; preceding Olivia lesson | Existing Olivia course (`olive-owl`) | Keep course and lesson ID |
| `olive-catalan-try-alone` | Independent bishop plan; preceding Olivia lesson | Existing Olivia course (`olive-owl`) | Keep course and lesson ID |

Chicky's planned first path now includes check and simple mate. Pawn, rook,
bishop, and queen movement/capture lessons and king safety follow the knight
lesson. Pippa's first developing-move exercise offers a shorter introduction
than the existing multi-move opening lesson. Tina now has a simpler
promotion setup. Tom needs a checked opening threat and response. Bruno needs
an inactive-piece planning exercise beyond his Scotch course. Olivia needs a
short fork/pin/defence puzzle. Monty needs a sourced historical analysis and a
verified-win entitlement. These are new content tasks, not replacements for
existing history.

## First reviewable implementation slice (implemented)

1. Define a versioned general `Course` contract in `study/content.py` while
   converting existing schema-1 opening records at load time. It should carry
   category, guide ID, ordered lesson IDs, objective, assumed knowledge,
   optional source game, optional entitlement, and an explicit completion /
   independent-practice policy. Validate distinct lesson IDs, references,
   publication state, and kind-specific source requirements. Document the
   format in `docs/CONTENT_FORMAT.md`.
2. Update course lists and details, progress denominators, Continue, Sources,
   scrolling, and return routes for one or many lessons. Pass the originating
   course ID through lesson entry and status calls. Make both Learn and a
   character page open the same course controller. Keep drafts unpublished.
3. Pilot one Chicky lesson: start with a sparse, checked board and one knight
   selection and destination action. Observable goal: select the knight and
   move it to a marked legal square, then repeat the idea without a source
   square cue on a related position. The guided prompt should explain
   piece-then-square input; hints and wrong-move feedback should describe the
   knight's L-shaped move without revealing the answer before help is asked.
   Use a stable new lesson ID, two reviewed steps (guided then independent),
   and a new Chicky course with an explicit completion policy. Validate both
   positions, branches, and text at all supported sizes before publishing.
4. Keep later character paths out of this first slice. After the pilot, review
   learner interaction and implement Pippa/Tina, then Tom/Bruno/Olivia. Add
   Monty's entitlement with a migration only when his course consumes it;
   insert/backfill it from verified wins without affecting the Master award.

## Checks for the first slice

- Loader tests: schema-1 compatibility; new 1-, 3-, and longer-course records;
  duplicate/missing lessons; unpublished draft exclusion; source validation by
  content kind. Preserve both existing course IDs and progress.
- Navigation tests: a shared lesson returns to its originating course; Continue
  and completion use the full lesson list; no hidden fourth lesson; unavailable
  Sources actions cannot open a missing game.
- Chicky lesson: `scripts.validate_content` accepts every PGN/FEN and reviewed
  branch; guided and independent attempts record assistance correctly. Check
  question, hint, wrong move, feedback, and completion at narrow/wide sizes and
  all three text sizes, including keyboard selection.
- Release checks after code changes: `pytest -q`, `scripts.validate_content`,
  `scripts.smoke`, representative screenshot inspection, then a wheel installed
  into a temporary environment for offline resource loading. Use temporary
  progress databases only.

## Verified result on 29 September 2026

- The full suite before this expansion passed 139 tests on Python 3.14.7 /
  pygame 2.6.1. The environment emits the existing pygame AVX2 build warning.
- Content validation and rendering smoke passed after this expansion. The
  catalog contains 22 games, 22 lessons, and three courses; all authored
  branches resolve legally. The focused expansion checks passed afterward;
  rerun the full suite before release.
- Reviewed the Chicky character, course, and lesson screenshots at narrow
  sizes, including 360 pixels with extra-large text. The character-page Learn
  action shares the navigation row to keep the story readable.
- Built the wheel without downloading dependencies, installed it under `/tmp`,
  and loaded its resources and course UI while running outside the checkout.
  This used the existing Python/pygame runtime, not a clean dependency install.
- Used temporary progress stores for checks. No new SQLite migration is needed
  for this slice. Existing course and lesson identities remain stable.

Next: observe the Chicky pilot, expand Tina's king activity and stalemate
fundamentals, then add Tom's first threat exercise. Monty's access
service, all seven complete paths, wider
accessibility work, and the advertised Python-support mismatch remain planned.
No learner observations or educational-effectiveness claims were made here.
The Python minimum was aligned with the tested CI baseline at 3.9 on
2 October 2026.

## Beginner expansion

Chicky now has seven lessons in order: Knight steps, Pawn steps, Rook lines,
Bishop diagonals, Queen routes, Keep your king safe, and A simple checkmate.
The movement lessons
introduce a guided move and then an independent try. The bishop exercise
accepts both available captures. Existing knight lesson IDs, revision, and
progress are retained;
the course now reports completion out of seven lessons and pages the list.

The pack now contains 27 games and 27 lessons. The initial expansion's nine
focused tests passed,
covering course formats, all bundled assisted/unassisted lesson paths, new
capture outcomes, saved completion, fresh-user entry, and course navigation.
Content validation and smoke passed. The three new lessons also loaded and
completed from a wheel installed under `/tmp`, outside the checkout.

Rendered question, hint, feedback, and completion at six sizes (360, 420, 600,
819, 821, and 980 pixels wide) and all three text scales. Inspected narrow
captures and a wide bishop exercise; explanations scroll at the smallest size.
Course page labels were shortened for narrow/large-text layouts. Queen moves
now use a straight guided move and a diagonal independent capture. King safety
introduces check and accepts every legal escape. Simple mate now uses a guided
queen setup and an independent checkmate. This expansion has not yet been
observed with learners.

The queen follow-up passed content validation and rendering smoke. Its guided
move, independent capture, wrong-move retry, and course pagination passed the
focused course/UI tests (31 tests). Narrow question and feedback screens and a
wide independent screen were inspected. An installed wheel loaded and completed
the new lesson offline outside the checkout. The full suite passed 140 tests
on 30 September 2026. Learner observation remains pending.

The king safety follow-up uses one guided king move, then a rook check with
three accepted escapes. It keeps the existing course ID and progress model.
Content validation, rendering smoke, 36 focused content/replay tests, visual
inspection at 360 and 980 pixels, and offline completion from an installed
wheel passed. The full suite passed 141 tests after this addition.

The simple mate follow-up adds one checked position and two reviewed steps.
The independent position has one mating move; other checking moves let Black
escape. Course pagination now reaches all seven lessons. The existing
`mate-or-stalemate` lesson remains a separate follow-up exercise.
Content validation, rendering smoke, 37 focused content/replay tests, visual
inspection at 360 and 980 pixels, and offline completion from an installed
wheel and the full suite (142 tests) passed. Learner observation remains
pending.

Pippa's one-lesson opening course starts from a checked position after central
pawns and knights have moved. A guided bishop move explains development; an
independent knight move asks the learner to choose a central square. Learn's
Openings page and Pippa's character page enter the same course controller.
Chicky and Pippa now keep an off-plan move on its starting square, show a short
"try again" message, and immediately accept another move without a Retry click.
Content validation, rendering smoke, narrow feedback inspection, all 144 tests,
and offline lesson completion from an installed wheel passed. No learner
observation has been recorded for Pippa yet.

Tina's one-lesson endgame course now uses a sparse board and two reviewed
steps: a guided pawn advance, then an independent queen promotion. Learn and
her character page open the same course. A different legal promotion leaves
the pawn on a7 and immediately invites another choice. The existing
`promote-the-pawn` lesson remains available as a later exercise.
The promotion chooser now names all four pieces in larger buttons, and the
Learn menu keeps its return label readable at narrow, extra-large text size.
Content validation, rendering smoke, visual inspection at 360 and 980 pixels,
and offline completion from an installed wheel passed. The full suite passed
146 tests; the final narrow-screen menu and promotion retry checks passed after
the label adjustment. Learner observation for Tina remains pending.

Tina's course now has a second lesson, Bring your king closer. The guided step
places the king beside its pawn. In the independent position, Black approaches
and either of two safe fourth-rank king moves completes the goal. The course
keeps its ID, and the promotion lesson keeps its revision and saved progress.
The position, PGN line, legal alternatives, and course references passed content
validation. Rendering smoke passed. Guided and independent prompts were inspected
at 360 pixels with extra-large text, and the guided prompt at 980 pixels. The
installed wheel loaded and completed the lesson outside the checkout. Learner
observation remains pending. The full suite passed 147 tests after this addition.

Tina's third course lesson reuses the existing `mate-or-stalemate` identity and
checked position. Its revision is now 3 because the exercise has Tina's coach
voice and records the final move as independent practice. The original lesson
remains in the general lesson list; the course keeps its ID and now reports
progress out of three lessons. The previous revision's saved records remain in
the progress store. Its answer arrow and target highlight were removed so the
independent question does not disclose the move. The wrong queen move explains
the stalemate draw and leaves
the position available for another try. Beginner lesson retries now keep the
coach's short encouragement while showing the authored move feedback in the
scrollable lesson panel. This matters here because the stalemate explanation
would otherwise be hidden by the generic retry message.
Content validation, rendering smoke, narrow and wide visual review, and
completion from an installed wheel outside the checkout passed. The full suite
passed 149 tests. Tina's revised lesson has not been observed with learners.

Tom's first opening course now reuses `black-against-e4` and its unchanged
synthetic game score. The guided first step answers 1.e4 in the centre. The
independent second step asks Black to notice White's knight attacking e5;
reviewed replies distinguish development, counterattack, pawn support, and the
weakening ...f6 move. The lesson ID is unchanged and its instructional revision
is 3. Its older progress records remain stored. The course is reachable from
Learn's Openings page and Tom's character page through the shared course view.
Content validation, rendering smoke, narrow and wide prompt inspection, narrow
wrong-move feedback inspection, and offline completion from an installed wheel
passed. The full suite passed 151 tests. Tom's exercise has not been observed
with learners.

Bruno's first middlegame course adds `bruno-activate-pieces` without changing
his existing Scotch course or saved progress. Its guided move develops the
waiting bishop; after Black responds, an independent move puts the idle rook
on the open c-file. Both positions are original and the lesson uses a checked
synthetic score. The Guided games page and Bruno's character page open the same
course. Learner observation remains pending.

Content validation and rendering smoke passed. The installed wheel loaded the
new course, completed both steps, and saved progress outside the checkout.
Narrow and wide screens were inspected, including the independent prompt and
wrong-move feedback. The full suite initially reported three catalog-count
assertions after adding the new game; its other 150 tests passed. Those counts
were updated, and all three affected tests passed on rerun. No learner session
has yet reviewed Bruno's wording or plan choice.

Olivia's first tactics course adds `olivia-knight-fork` and retains her Catalan
opening course and existing progress. Its original position asks for a knight
check that attacks both king and queen. After the king moves, the learner takes
the queen; the synthetic score includes Black's rook recapture to support the
exchange explanation. The puzzle is available from Learn's Guided games page
and Olivia's character page through the shared course controller. Learner
observation remains pending.

Content validation, rendering smoke, and all 155 tests passed after Olivia's
addition. The installed wheel loaded and completed her course offline outside
the checkout. The Guided games hub, course controls, and puzzle controls fit at
360, 420, 600, and 980 pixels across all three text scales; narrow and wide
puzzle, follow-up, feedback, and completion captures were inspected. No learner
observation has been recorded for Olivia yet.

Monty's first historical course uses the complete [Lasker–Bauer Amsterdam 1889
score](https://en.wikipedia.org/wiki/Lasker_versus_Bauer,_Amsterdam,_1889),
with recorded player identities omitted in the packaged PGN and original
teaching text. Its guided question predicts the first bishop sacrifice; an
independent question predicts the quiet rook lift after Black has answered the
checks. Learn and Monty's character page show the one-win lock plainly.
Access is derived from the existing verified-win ledger, including schema-10
backfilled wins, and stays separate from the two-colour Master award. No new
schema migration is needed.

The starter pack now has 31 games, 31 lessons, and nine published courses.
Content validation and rendering smoke passed. The full suite passed 157 tests;
after that run started, a provenance rejection test and keyboard assertions
were added and passed in focused reruns. The delivery wheel loaded the complete
score and lesson offline outside the checkout. Locked and unlocked routes fit
at four window sizes and three text scales; narrow and wide lock, lesson,
course, and source views were inspected. Replay return and saved completion
were checked with a temporary progress database. Monty's analysis has not yet
been observed with learners. The first teaching slice now exists for all seven
characters; expanding their paths and learner review remain next work.
