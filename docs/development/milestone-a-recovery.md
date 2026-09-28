# Milestone A1: saved challenge recovery

The first update slice adds read-only verification of active challenge saves.
The verifier checks saved JSON shape, legal move order, opponent policy record,
position, and commentary before a session is published. An invalid save opens a
recovery screen with Retry, Export, and Archive and start again. Archiving keeps
the original match and policy, records a reason, and clears the active slot in
one transaction. The Play menu provides access to archived saves and export
after restart. A database read/write failure offers retry or safe return and
does not imply that the match is invalid. Failed move and resignation saves
keep the last committed board and require an explicit retry or return.

Schema 9 and its old-data and failure policy are recorded in
[ADR 0002](../architecture/0002-challenge-recovery.md). Existing challenge
badges and history are not changed by this slice. The next milestone A task is
the calibration command and measured comparison of adjacent opponents.

Verification on 28 September 2026: all 120 tests passed across the challenge
and progress, widget, and remaining chess/study test batches. Content validation
and smoke checks passed. Recovery, archive, and export screens were inspected at
360×700 with extra large text; control bounds were checked at 360×700, 600×600,
and 980×760 across all three text sizes. The first combined test process ended
with exit 143 before a result; every test file was then run successfully in
shorter batches. Learner observation and calibration remain pending.
