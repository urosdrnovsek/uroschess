# ADR 0002: Preserve invalid challenge saves during recovery

Status: Accepted for the challenge recovery update

## Data contract

Schema 9 adds `challenge_recovery(match_id PRIMARY KEY, reason_code,
diagnosed_at, archived_at, original_updated_at)`. Its match ID refers to an
existing `challenge_matches` row. A recovery row is written only when the owner chooses
to archive an invalid active match. The original move JSON, FEN, policy record,
seeds, and commentary stay unchanged. The original update time is retained in
recovery metadata. Archiving changes the match state to
`abandoned` and clears the active slot in the same transaction. It cannot earn
a badge. Retrying verification or exporting does not change progress.

Fresh databases and upgrades create the same table. Existing matches are not
marked invalid by migration, because validation depends on the saved policy and
current verifier. Schema version advances only if creation succeeds. A failed
archive rolls back both the state change and recovery row. Unknown newer schemas
remain unsupported and are never reset.

An export is a local JSON copy of the raw match and policy rows, the original
pre-archive match payload, and the diagnosis when available. It writes to a
caller-selected destination and does
not alter the database. The UI uses a named file beside the progress database
and shows that destination to the learner. Database I/O errors are reported as
retryable errors; they are never treated as evidence of corruption.
