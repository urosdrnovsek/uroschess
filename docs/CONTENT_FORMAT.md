# Starter content format

`chess_game/content/starter/manifest.json` lists games, lessons, and the
beginner `learning_path`. A game is a PGN record; a lesson refers to a game by
`game_id` and has its own stable `lesson_id`. Multiple lessons may share one
game. Replays use the game list, while lesson libraries and saved progress use
the lesson list.

`players.json` lists the fictional coach identities. `courses.json` orders
three lessons for each opening course, names its player, records prerequisites,
and carries two separate sources: `association_source` provides background on the opening; `source_game` identifies an anonymized historical score.
Course lessons refer to that game with `related_source_game_id`. A synthetic
lesson's board is labelled as a practice position and does not claim to show
the archival game's exact moves. `commentary_source` identifies Uroschess teaching
authorship. Portrait attribution stays with the player record.
Published courses require a packaged `source_game` PGN entry with the same
stable ID and source URL. Source games have category `source_game`; they appear
once in **Watch games** and never in lesson lists. The course's **Sources**
screen shows attribution, opens the reference links, and replays the
packaged score offline. Learn remembers the last course or lesson list in app
settings and offers a return button after restart.

Lesson schemas 1 and 2 still load. Schema 3 adds `coach_player_id`,
`content_kind`, `related_source_game_id`, and `initial_help`. A step may specify
`practice_mode: "independent"` to remove automatic source-square cues. A
reviewed opponent reply may provide `next_prompt` and its own `hints`; the
controller shows those only after the reply has happened. Hints and answer
reveals are explicit actions. Keep the prose short enough for 360-pixel
windows and review every accepted move and feedback claim on the board.

Progress schema 5 keeps the existing lesson totals and schema-4 `step_progress`,
keyed by lesson ID, content revision, and step ID. Its `outcome` is
`unresolved`, `helped`, or `independent`. Migration preserves older lesson
records without inventing step outcomes. A child who used help can repeat an
exercise independently later. A multi-move exercise restarts its current step
when the app is reopened; individual in-step moves are not checkpoints. The
`active_assisted` flag preserves help used in the current unfinished attempt
across restarts. Explicit Restart clears it without erasing lifetime counts.
Schema-4 unfinished records with prior help totals are restored conservatively
as helped, because the old format cannot identify the helped step. Completed
history and earlier content revisions remain available.

Progress schema 9 adds `challenge_recovery` for archived invalid challenge
matches. A recovery row records the saved match ID, verifier reason, diagnosis
time, archive time, and original update time. The original match and policy
rows remain available;
archiving changes only the match state and update time. The active slot is
cleared in the same transaction. Export produces a local JSON copy of the raw
match, policy, and recovery rows. Database failures are retryable and never
mark a match invalid. See [ADR 0002](architecture/0002-challenge-recovery.md).

Progress schema 10 adds `challenge_win_events`, keyed by match ID. Every
verified human checkmate victory in Character Challenge creates one event in
the same transaction as the terminal match and any new badge or Master award.
Rematches create new events but not duplicate badges. Draws, losses,
resignations, unfinished and archived matches, imported replays, and casual
games do not create events. Migration checks retained legal histories, final
positions, human winner, commentary and supported recorded policies before
backfilling; unsupported records keep their existing badges without an inferred
medal. The UI derives the seven medal counts from this ledger and caches them
outside drawing. See [ADR 0003](architecture/0003-challenge-win-events.md).

Course prerequisites use stable lesson IDs. An unfinished prerequisite adds a
Practise basics route from the chosen player's page; the course remains open.
Course browsing remembers its page. A finished player lesson's Watch source
game action opens the linked historical PGN and returns to the same completed
lesson. Lessons without a historical link offer Replay practice instead.

Run `.venv/bin/python -m scripts.validate_content` to resolve all PGN paths,
FENs, and reviewed branches before shipping. Run the test suite and build a
wheel to ensure every JSON, PGN, and portrait resource is packaged.
