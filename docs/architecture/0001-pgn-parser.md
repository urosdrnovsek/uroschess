# ADR 0001: Keep the teaching core MIT-compatible

Status: Accepted for the first teaching release

## Context

The teaching upgrade needs PGN headers, comments, variations, annotation
glyphs, and games that begin from a FEN position. The current parser only
returns a flat main-line move list. `python-chess` supports the required game
tree, but it is distributed under GPL-3.0-or-later while Uroschess is MIT.

## Decision

Uroschess will implement the required standard-chess PGN game tree in this
repository and keep it behind `chess_game.study.pgn_service`. It will use the
existing board, legal-move, SAN, and FEN code through `ChessAdapter`.

The parser will be strict for bundled teaching content: damaged games must
produce useful diagnostics rather than silently skipping tokens. The first
version only needs standard chess and the PGN features used by the teaching
application. Unsupported constructs must be reported explicitly.

Stockfish and tablebases may be used as optional authoring tools. They are not
runtime requirements for bundled lessons. Any later decision to distribute a
GPL dependency or engine requires a separate license and packaging review.

## Consequences

- The application and its required Python dependencies remain compatible with
  the repository's MIT distribution model.
- PGN parsing will require focused tests for comments, nested variations,
  annotations, custom starts, multiple games, and error locations.
- The parser remains replaceable because UI and lesson code depend on study
  models and the adapter rather than parser internals.
- This is more implementation work than adopting `python-chess`, so the scope
  is limited to features exercised by the product and its content packs.
