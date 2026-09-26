# Milestone 1: reliable annotated game viewer

Milestone 1 adds the first complete learning path without coupling recorded-game
navigation to the computer opponent.

## Delivered

- A strict internal PGN importer for standard chess, including headers,
  comments, nested variations, numeric and symbolic annotations, multiple games,
  recorded results, and `SetUp`/`FEN` starts.
- Immutable game-tree models and a replay controller that can rebuild any
  recorded position exactly.
- First, previous, next, last, direct move selection, board flip, autoplay, and
  autoplay speed controls.
- A packaged content manifest and a complete anonymized historical score.
- A game library, source attribution, concise notes, explicit content errors,
  and a reusable study-panel renderer.
- Headless tests that cover parsing, alternate lines, FEN starts, random access,
  the packaged game, mouse navigation, autoplay, and the no-AI viewer boundary.

## Architecture

`chess_game.study.pgn_service` imports PGN into immutable models.
`chess_game.study.replay` owns navigation and derives positions from the source
tree. `chess_game.views.study_view` only draws the replay panel. The existing
`BoardView` draws the supplied board in both normal play and study mode.

Content is loaded through `importlib.resources`, so the same files work from a
checkout or an installed package. One invalid library entry is reported without
hiding other valid games.

## Deferred to milestone 2

The next phase turns selected positions into a guided lesson with objectives,
prompts, learner move attempts, feedback, hints, and a takeaway. Opening advice,
endgame drills, progress storage, and larger content packs remain later phases.
