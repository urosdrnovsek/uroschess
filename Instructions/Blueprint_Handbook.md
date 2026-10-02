# Uroschess blueprint handbook

Updated: 2 October 2026. Earlier baseline: `b078911`.
This is the single local planning handbook. This file is tracked for handoffs;
the other files in `Instructions/` remain ignored by Git. Update this document
in place; keep technical contracts in the existing
`docs/` files instead of copying them here.

## Purpose and summary of the two earlier blueprints

Uroschess is a small offline desktop chess app for casual play and short
lessons. The current strategy lessons assume children already understand piece
movement, check, and checkmate. Chicky now has a seven-lesson beginner path
covering piece movement, captures, king safety, and simple mate. Help learners
notice threats, make a plan, and explain a move. Keep the public description
modest and factual.

- **App upgrade blueprint:** retain ordinary play, add reliable game replay,
  guided questions, hints, temporary exploration, and saved progress. Separate
  chess logic from drawing, verify instructional content, and observe learners
  before building a much larger collection.
- **Coach course blueprint:** use a consistent illustrated guide, short opening
  courses, position-specific feedback, and a related exercise to try alone.
  Preserve course identity and navigation, distinguish helped and independent
  attempts, and keep questions usable in small windows.

The earlier real-player concept is retired. Use Bruno the Bear, Olivia the Owl,
and the other original fictional characters. Do not reintroduce
famous players' names, likenesses, attributed advice, or endorsement language
in app-facing text, assets, or screenshots. Historical source citations belong
in provenance documentation, never as claims that a character played or
commented on a recorded game.
The old milestone logs and already-fixed defect lists are deliberately omitted.

## What already exists

- Local two-player chess, a computer opponent, and computer-versus-computer play.
- Character Challenge: seven offline opponents, saved matches, White-then-Black
  badges, permanent unlocks, repeat-win medals, and the Uroschess Master award.
  Invalid saves have preserved recovery, and Master celebration needs explicit
  dismissal.
- All seven characters have distinct general quotes and match comments.
  Meet the characters gives each one a portrait, story, and favourite piece;
  the changing menu portrait keeps the same size across standard menu views.
- Learn / Play / Watch games navigation. Learn now opens a portrait gallery
  for all seven character guides, with a short description of each guide's
  topic. A character page holds their courses and related older practice
  lessons; all 31 lessons remain reachable without a separate category menu.
  The starter pack has 31 games, 31 lessons, and nine published courses; some
  game records are practice lines. Fresh learners can start with Chicky, while
  the other guides are directly available. Monty's
  historical analysis opens after one verified win against him with either
  colour; this is separate from the two-colour Master award.
- Annotated replay, reviewed move sequences, hints, answer reveal, retry,
  exploration, and independent practice. Historical scores are anonymized and
  distinguished from original practice positions.
- Local SQLite progress and settings, assistance preserved across resume,
  course prerequisites, paginated courses, and return-to-origin navigation.
- Resizable layouts, three text sizes, keyboard focus, board styles and sound
  settings. The latest lesson panel has a compact coach, one visible question,
  contextual feedback, and back/next lesson arrows beside the step label.
- A shorter README and refreshed screenshots, including the character gallery.
  The first seven-character and menu work was committed as `8b0b355`.
  The latest lesson slice passed content validation, rendering smoke, an
  installed offline wheel check, and 157 tests in the full suite; focused
  checks passed after the final test additions. These checks do not establish
  lesson quality or calibrated opponent strength.

Learner observation is still pending. A multi-move exercise resumes at the
start of its current step, preserving help use; it does not resume every move.
Keyboard support does not provide native screen-reader access.

## Design rules to preserve

1. Teach one idea at a time: see the position, try a move, understand its
   consequence, try a related position, remember one takeaway. Aim for short
   sessions around three to five minutes and adjust after observing children.
2. Keep the question and next action obvious. Show only the explanation, hint,
   or feedback needed now. Put optional detail behind an explicit action.
   Coach encouragement must not repeat the teaching text or disclose answers.
3. Use concrete language and introduce chess terms when needed. A useful
   explanation names a piece, square, threat, or consequence on this board.
4. A legal alternative is not automatically wrong. Distinguish a reviewed good
   answer, a mistake, and a move outside the exercise's reviewed branches.
   Explain the lesson goal kindly; keep exploration available.
5. Record hint/reveal use honestly. Helped completion is useful progress;
   neither it nor one independent answer proves mastery. Avoid shame, public
   rankings, compulsory streaks, and pressure to keep playing.
6. Keep lessons offline and ordinary play easy to reach. Use original prose
   and art; keep content provenance accurate without crowding the lesson.

## Future upgrades, in priority order

### Character Challenge: implemented, with follow-up work

The original challenge design is in
[`character-challenge.md`](character-challenge.md); its five-character roster
and proposed search tuning are historical. The implemented order is Chicky,
Pippa, Tina, Tom, Bruno, Olivia, and Monty. Each opponent requires a White win
and then a Black win before the next unlocks. A migration preserves older
access and Master awards. Pippa searches to depth one on 50% of turns, Tina to
depth one on 70%, Tom to depth one on 90%, and the remaining turns for these
three are random legal moves. Bruno searches to depth two, Olivia has a
two-second/depth-32 cap, and Monty retains the six-second/depth-64 Max policy.
These are implementation settings, not measured ratings. Real-game calibration
and learner observation remain pending.

The main menu has a changing portrait and quote, and Meet the characters has
the seven stories and favourite pieces. The menu labels and portrait sizing
were adjusted before commit `8b0b355`; at short heights, crowded menus omit
the portrait to keep their controls visible. The README screenshots were
refreshed with that commit.

Prioritize these Character Challenge improvements before expanding the mode:

1. **Measure and tune opponent strength.** The reproducible, colour-balanced
   calibration command and a short initial diagnostic are complete. Of 36
   diagnostic games, 35 were truncated and one ended from an imbalanced tactical
   position, so run a longer batch before deciding
   whether Pippa, Bruno, or Olivia need tuning. Retain Monty's Max policy.
   A 12-game, 80-ply follow-up on three adjacent pairs had no search failures
   after a timeout fix, but six games were truncated. Do not advertise Elo
   ratings without evidence.
2. **Saved-match recovery: implemented and verified in test batches.**
   Invalid active saves now have a dedicated explanation, retry, export, and
   transactional archive path. The archive remains exportable after restart.
   Database failures have retry and safe navigation without marking a record
   corrupt. Failed move and resignation writes keep the committed board until
   retry or return. Schema 9 preserves recovery evidence and the original match
   update time. All 120 tests passed across batches; content validation, smoke,
   and narrow visual checks passed. Learner observation remains pending. See
   `docs/development/milestone-a-recovery.md` for this slice.
3. **Reward screens and repeat-win medals: implemented.** The result view
   distinguishes a new colour badge from a prior badge, shows the medal count
   and next opponent, and requires explicit Master celebration dismissal.
   Schema 10 stores verified repeat wins; Medals opens all seven character
   counts on one page. See `docs/development/calibration-and-rewards.md`.
4. **Add a short post-game review.** Replay the saved match and highlight one or
   two checked moments that help the learner understand a choice. Keep review
   separate from live challenge play; do not present an unreviewed engine guess
   as authored coaching.
5. **Observe real players.** With an adult, watch children choose an opponent
   and colour, interpret locked cards and badges, reread comments, resume a
   match, and use mouse and keyboard controls. Record findings in
   `docs/LEARNER_REVIEW.md` and improve observed difficulties before claiming
   the journey is easy for children to use.

These follow-ups take priority over adding more opponents or online features.
The earlier “Play from here” proposal below remains a separate substantial
feature. Existing implementation safeguards and learner observations still
apply.

### Repeat-win character medals: implemented reward

Give every character a private collection on the beginning screen, beneath
the main menu. Each verified win against Chicky earns one small, circular
medal with Chicky's face in its centre. Show one small medal per win for wins
one through nine. On the tenth win, replace those small medals with one larger
gold circular medal bearing Chicky's face. Apply the same rule independently
to Pippa, Tina, Tom, Bruno, Olivia, and Monty. Further wins keep the gold
medal; a separate lifetime count may still rise.

Count completed human victories against that character with either colour,
including rematches. Keep these counts separate from the unique White/Black
unlock badges and the Master award: one win contributes to both systems when
eligible, but a repeat win still contributes to the medal count. Count each
verified match ID once, including after save/resume or restart; draws,
resignations, abandoned games, and unverified records earn nothing. During
migration, credit past wins only when their stored match result can be
verified. Never invent extra wins from the two colour badges.

The opening menu has a Medals button. Its collection shows all seven
characters on one page, using two columns for short or wide windows and one
column for taller narrow windows. Each card shows a text count and medal art.
The smallest window uses tiny circles, so check their recognisability with
players; the count and gold label remain visible. Keep the reward optional and
local, without streak pressure.

### Character-led lessons: first slice implemented, expansion pending

Every character now has a first teaching slice in Learn and on their character
page. The 31-lesson pack is not the complete set of paths described here. Keep
ordinary lesson browsing available regardless of challenge progress, with the
one Monty exception below. The general course loader, variable-length course
pages, stable progress IDs, and return routes serve all seven guides.

| Character | Current slice and next content direction | Voice and first exercise |
| --- | --- | --- |
| Chicky | Seven beginner lessons cover movement, captures, king safety, and mate; review with novices before adding more. | Curious questions and guided board moves. |
| Pippa | First opening lesson develops a bishop and knight; later centre and king-safety work remains. | Sweet encouragement and useful development. |
| Tina | Three-lesson endgame course covers promotion, active king, and stalemate; transfer exercises remain. | Gloomy but kind endgame guidance. |
| Tom | First threat lesson reuses `black-against-e4`; more unfamiliar replies remain. | Comically angry at idle pieces; choose a sound opening reply. |
| Bruno | First middlegame lesson activates bishop and rook; exchanges and rook or pawn endings remain. | Calm, fatherly planning. |
| Olivia | First tactics lesson teaches a knight fork; pins, defence, and mating patterns remain. | Observant questions around a reviewed position. |
| Monty | First historical analysis predicts two moves from a sourced 1889 tournament score; learner review remains. | Proud commentary that credits both sides, without claiming to have played. |

Monty refuses to teach until the learner records a verified win against him
with either colour. That first win permanently unlocks his analysis; earning
the Uroschess Master title still requires both colours and remains a separate
reward. Existing verified Monty wins must count after migration. State the lock
and its requirement plainly, and let the learner revisit the analysis freely
once unlocked. Choose an authentic, checked tournament score with a documented
source. Monty calls it a favourite game, not a game he played; follow the
existing policy of anonymizing historical player identities in the app. This
is implemented through the schema-10 verified-win ledger; incomplete, resigned,
and invalid matches cannot unlock it. The score and citation are recorded in
`docs/development/upgrade-preparation.md`.

The first implementation pass covered the content and access slices below;
learner observation in step 6 remains open:

1. Map existing lessons to these topics and identify the missing exercises.
   Write a short sequence and one observable goal per character. Check the
   learner's assumed knowledge before making Chicky's path the suggested
   starting point; existing strategy learners must still reach their courses.
2. Extend course metadata and the Learn/character-page navigation so the same
   lesson controller can serve seven guides and variable-length paths. Reuse
   stable character IDs, lesson IDs, revisioned progress, and return routes.
   Avoid a separate hard-coded screen or progress system per animal.
3. Pilot Chicky's movement path, then Pippa and Tina's fundamentals. Test
   whether the current move-question interaction is clear for children who
   have never moved a piece; add a small guided interaction only if needed.
4. Add Tom, Bruno, and Olivia as authored positions with checked replies and
   helpful feedback for legal alternatives. Reuse and revise relevant current
   lessons instead of duplicating them under a new character name.
5. Add Monty's win-based entitlement and one sourced game analysis. Verify
   unlocking, persistence, migration, replay return, and that incomplete,
   resigned, or invalid matches cannot unlock it.
6. Validate every position and continuation, inspect all text sizes and narrow
   layouts, check the installed offline package, and observe learners using
   each path before expanding its lesson count. The automated, visual, and
   installed-package checks passed for the first slices; learner observation
   is still pending for all seven.

Further lessons are proposed improvements, not features promised for the next
release. Reproduce a suspected problem in the current app before treating an
old observation as a bug.

### Usability checks alongside new lessons

- [ ] **Observe children using it.** With an adult, try starting a lesson,
  making a mistake, asking for help, returning later, and solving a related
  position. Record confusing words and actions in `docs/LEARNER_REVIEW.md`.
  Improve the observed difficulties; do not manufacture learning results or
  delay unrelated repairs while waiting for feedback.
- [ ] **Finish the lesson interaction audit.** Review question, hint, wrong
  answer, automatic reply, exploration, and completion states. Check that
  prompts match the board, labels describe their destination, and coach clicks
  or the N shortcut cannot bypass help tracking or create duplicated text.
  Offer optional “Why?” detail only if learners need it.
- [ ] **Improve small-window usability.** Prioritize a board large enough to
  select pieces, fully readable questions, generous controls, and predictable
  scrolling. Test narrow and short windows at every text size, including near
  the layout breakpoint. If the minimum size cannot work well, define an
  honest supported minimum instead of compressing everything indefinitely.
- [ ] **Make starting and returning simpler.** Test the existing beginner path,
  Continue, prerequisites, and Back/Menu labels with fresh and returning users.
  Add a brief dismissible “select a piece, then a square” demonstration if
  needed. Teach one unfamiliar word at a time through optional explanations.
- [ ] **Improve visual accessibility.** Check contrast across themes and piece
  colours, visible focus, non-colour feedback, and button targets. Consider a
  plain high-contrast board and reduced-motion setting. Explore optional local
  read-aloud separately; test with actual users before making accessibility
  claims. Reassess UI technology if screen-reader support becomes a requirement.

Done when a child can find a lesson, understand the task and feedback, and
return to it with less adult direction. Visual checks must confirm readable
text and usable board space, not merely that button rectangles fit.

### Further practice and retention

- [ ] **Play from here — subsequent substantial feature.** After one
  lesson, offer a short practice game from a related position with one goal
  and roughly three to five learner moves. Start with one carefully checked
  goal and review one concrete moment. Clone the position, retain the return
  route, cancel stale computer moves, and store this result separately from
  lesson completion. Define what leaving/resuming does before implementing it.
- [ ] **Your next five minutes.** Offer an optional small selection: a next
  lesson, a revisit, and a related position. Use stable concept IDs, actual
  attempt outcomes, and completion times. Browsing must not count as practice.
  Keep selection deterministic and local; preserve free choice of lessons.
- [ ] **Targeted review.** Revisit helped answers and mistakes, with varied,
  authored positions. Keep review state across restarts and content revisions.
  Show progress in plain language; do not present a score as Elo or a validated
  measure of mastery. Build this together with the short-session selection
  rather than creating two competing progress systems.
- [ ] **Strengthen the strategy sequence.** Connect development and king
  safety to threat checks, undefended pieces, improving an inactive piece,
  open files, pawn breaks, sensible exchanges, and simple defence. Add short
  fork, pin, and mating exercises through the existing lesson controller.
  Teach both colours and unfamiliar replies, not only memorized opening moves.
- [ ] **Extend endgames gradually.** Start with clearer transfer exercises for
  current mates, promotion, and king activity. Later consider key squares,
  passed pawns, and elementary rook endings. Verify the goal and continuations
  for every altered position; do not grade arbitrary moves by a shallow score.
- [ ] **Make the computer a useful practice partner.** Evaluate beginner
  difficulty by actual play, not just thinking time. Consider controlled,
  understandable mistakes, optional takebacks, and one short explanation after
  a game. Keep engine strength work behind learning and usability priorities.

Done when the new practice goal is checked, returning to the lesson preserves
its state, and a learner can attempt the idea in a different position. Expand
the content only as its wording and interaction prove useful.

### Later: make the project easier to maintain and share

- [ ] **Content authoring tools.** Start with a local preview/validation command
  for PGN/FEN, reviewed branches, and the longest text at supported sizes.
  Keep drafts out of published courses; check IDs, revisions, sources, and
  packaged exports. Add an editor only if authoring needs justify it.
- [x] **More flexible courses.** The loader and renderer now support variable
  lengths and all seven guides through the existing catalog. Add
  filtering/search only when browsing becomes difficult.
- [ ] **Simpler internals.** Extract navigation, lesson presentation, and play
  lifecycle responsibilities from `ui.py` in small changes. Keep study models
  independent of pygame; avoid database work during drawing. Preserve existing
  route, assistance, progress migration, and stale-AI regression coverage.
- [ ] **Reliable local data and import.** Improve actionable recovery messages,
  progress backup/export, and deliberate reset controls. Consider separate
  anonymous local profiles for shared computers if families need them. Later,
  improve PGN file selection and optional personal-game review without uploads.
- [ ] **Chess correctness.** Audit interruption/cancellation, make/undo safety,
  special moves, import errors, and draw handling as those areas change. Verify
  claimable versus automatic draw rules before teaching them. Keep unreviewed
  engine suggestions separate from authored lesson assessment.
- [ ] **Installation and releases.** Test a clean installation outside the
  checkout, provide useful startup errors, and align advertised Python/platform
  support with evidence. Add content validation and installed-package checks
  to CI; publish clear release notes and tested installation instructions.
  Consider desktop packages and other operating systems after testing them.
- [ ] **Presentation and adult guidance.** Keep README screenshots current and
  the description modest. Add a short parent/teacher guide explaining starting
  level, a suggested session, and what progress means. Keep visual style and
  terminology consistent; make issue reports easy without requesting child data.
- [ ] **Languages and optional services.** Separate UI strings for translation
  when a language is requested; review chess wording and layout in that language.
  Optional local analysis or read-aloud can follow a concrete need. Accounts,
  cloud sync, online chat, online multiplayer, and a web/mobile rewrite are not
  current priorities. Avoid adding infrastructure solely for speculative growth.

## Implementation and content safeguards

- Inspect the current checkout and preserve user work. Use temporary progress
  stores for tests; never reset the owner's learning history to exercise a flow.
- Keep recorded games immutable. Replay, lessons, exploration, and ordinary
  play have separate state; returning restores the correct originating context.
- Use stable IDs and intentional content revisions. Preserve old progress;
  migration must not turn unknown or helped outcomes into independent success.
- Update board data, expected FEN, reviewed branches, hints, and feedback
  together. Legal moves alone do not establish instructional accuracy. Review
  what the board actually demonstrates and keep answers hidden until needed.
- Keep authorship/source records accurate and original practice clearly marked.
  Adding tools or imported material requires checking their current terms and
  compatibility with the project's existing dependency policy. Keep optional
  authoring tools out of the normal offline lesson requirements.
- Run computer work outside the UI loop; match results to the current session
  and position, discard obsolete work, and handle failure without freezing.

## Verification and keeping this handbook useful

For a change, run the relevant checks. For a release candidate:

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m scripts.validate_content
.venv/bin/python -m scripts.smoke
```

For visible changes, run `scripts.update_readme_screenshots` as a Python module
and inspect representative captures. Include question, hint, feedback, and
completion states at wide/narrow sizes and all text sizes. Check keyboard and
mouse navigation. Build and install a wheel in a temporary environment outside
the checkout and verify that lessons, games, and portraits load offline.

Use `docs/CONTENT_FORMAT.md` for data/progress contracts,
`docs/development/multi-move-exercises.md` for exercise trees, and
`docs/LEARNER_REVIEW.md` for learner observations. Keep this handbook focused on
direction and remaining work; replace obsolete status instead of appending
another handoff log. Record actual checks and remaining limitations, and follow
the owner's current commit/push instructions.

## Start here after the 2 October 2026 release audit

1. Read `git status --short` before editing and keep any user edits. The
   1 October lesson work is in commit `5330131`; the 2 October release audit
   remains in the working tree. Read the last section of
   `docs/development/upgrade-preparation.md` for the exact Bruno, Olivia, and
   Monty implementation and verification notes. The source of truth for course
   metadata is `chess_game/content/starter/courses.json`; Monty's access check
   is in `chess_game/ui.py` and reads `collection_counts` from verified wins.
2. Begin with **learner review, not another new lesson**. Use
   `docs/LEARNER_REVIEW.md` and a fresh temporary progress profile. Have a
   learner choose Chicky's portrait and try his first lesson without coaching,
   then find Pippa's first course; ask them to move, use help or retry, leave, and
   resume. Record exact words/actions and window/text size, without personal
   details. Do not claim this review happened until it actually does. After
   these two, observe Tina's promotion and Monty's locked card when practical.
3. If no learner is available, start the lesson interaction audit at Chicky's
   first course: inspect question, wrong move, hint, answer, automatic reply,
   exploration, completion, and return states at 360 pixels and each text
   size. Compare the current board and copy; reproduce any problem before
   changing it. Then repeat for Pippa, Tina, Tom, Bruno, Olivia, and Monty.
   Record findings in `docs/LEARNER_REVIEW.md` as an internal audit, clearly
   separate from learner observations. Fix the first concrete confusion found
   and verify its saved progress and return route.
4. Before handing off a change, run `.venv/bin/python -m scripts.validate_content`
   and `.venv/bin/python -m scripts.smoke`, run focused tests for altered flows,
   then inspect the affected narrow and wide screens. Run the full suite and
   offline wheel check for a release candidate or a change that affects shared
   lesson loading or packaging. Update the status here and in
   `docs/development/upgrade-preparation.md`.

The current pack has 31 games, 31 lessons, and nine courses. The
[release audit](../docs/development/release-audit-2026-10-02.md) records a
successful offline wheel check, content validation, smoke, responsive screen
review, and 160 passing tests. None of the seven teaching paths has a recorded
learner observation. The 12-game, 80-ply calibration follow-up had no search
failures but six truncations; opponent strength remains unproven. The post-game
review remains a separate Challenge follow-up.

The later Learn menu redesign routes through seven portrait cards. Course
membership still comes from `chess_game/content/starter/courses.json`; the ten
older lessons outside published courses are assigned to guides for navigation
in `GUIDE_LESSONS` in `chess_game/menu.py`. Their IDs, revisions, and saved
progress remain intact. Review the guide descriptions and the new route with
learners; visual checks alone do not establish that the topics are clear.
Content validation, rendering smoke, and all 161 tests passed for this menu
change; the affected Learn tests also passed after the final layout adjustment.
The later lesson navigation change adds back and next arrows to every lesson
state. The arrows stay within one character's teaching path, preserve progress
when switching, and show an inactive direction at the first or last lesson.
