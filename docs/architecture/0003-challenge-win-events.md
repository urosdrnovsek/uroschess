# Challenge win events and medals

Schema 10 adds `challenge_win_events(match_id PRIMARY KEY, opponent_id,
human_color, earned_at, verification_revision)`. Each row refers to one retained
`challenge_matches` row. It records every verified human checkmate victory,
including rematches, independently of the one badge per character and colour.
The terminal match update, win event, badge, and possible Master award share one
SQLite transaction. A repeated terminal callback cannot create another event:
finished matches are immutable and the event key is the match ID.

The 9-to-10 migration backfills only retained finished challenge records whose
opponent and policy are supported, whose complete move history is legal, whose
final FEN is correct, and whose final position is a human checkmate victory.
Chicky's seeded moves can be checked exactly. Search choices are not reproduced:
historical time-limited searches are nondeterministic, so the recorded policy
and legal challenge history are the available provenance. Records without that
provenance are skipped. Existing badges and the Master award are preserved even
when a corresponding historical medal cannot be verified. Fresh databases start
at schema 10 with an empty event table. Migration and backfill are atomic; any
error rolls them back and leaves the old schema version intact.

`medal_summary` is a pure projection of a count: zero is labelled empty, counts
one through nine show that many small circular portraits, and ten or more show
one larger gold portrait plus the independent lifetime count. The UI queries
counts on navigation or a saved move, then draws from memory.
