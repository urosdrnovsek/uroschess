# Learner review

The automated checks cover board positions, saved progress, navigation, and
layout. A short session with a child and an adult can show whether the wording
and controls are easy to use. Record where the child hesitates; do not treat
passing tests as evidence that a lesson teaches well.

Start with fresh progress. Let the child choose a lesson in **Learn** and use
hints if they want. Watch without directing them:

1. Can they find and start a lesson?
2. Can they tell whose move it is and what the question asks?
3. After a move, can they find the feedback and decide what to do next?
4. Do **Hint**, **Show answer**, **Try again**, and **Lessons** mean what they
   expect?
5. Can they leave and find their saved progress again?
6. Can they tell that a practice position and a recorded game are different?
7. Do the back and next arrows help them move between a character's lessons?

Ask what they learned about the position, which words were unclear, and whether
the text size and window layout helped. Keep feedback anonymous; the app does
not need a child account for this review.

## First observation round

Status: **not conducted**. The implementation and automated checks do not
establish teaching effectiveness or suitability for a particular age.

Arrange five short sessions with a child and an adult present. Use anonymous
labels A–E, fresh local progress, and about 15 minutes per session. Do not
collect names, ages precise enough to identify a participant, recordings, or
accounts in the repository. Let the adult end the session whenever needed.

1. Ask “How would you start learning?” Observe whether the home shortcut and
   Chicky's course make sense without directions.
2. Try Knight steps. If the learner chooses a valid alternative, observe
   whether the feedback distinguishes a legal jump from the requested move.
3. Open **A knight on a new square** from Chicky's practice lessons. Ask the
   learner to describe the jump before moving. Record whether they succeed
   independently, with a hint, or after seeing an answer.
4. Leave a lesson, close the app, and return. Observe whether **Continue
   learning** resumes the task they expect.
5. Play a short challenge, resign if necessary, and open **Review match**.
   Observe whether the explanation and **Practise** action make sense.
6. For learners who already know rook moves, try Bruno's **Find a file on
   your own**. Ask what makes the chosen file open.

Use the same prompts for everyone. Avoid correcting hesitation immediately;
record what happened before giving help. Use the text size and window size the
learner prefers. Ask “What would you do in another position?” afterwards.

Copy [the observation sheet](learner-session-template.md) once per anonymous
session. After the first round, group repeated difficulties, choose the three
most consequential changes, and repeat those tasks in another round. Report
observations as a small qualitative sample, without claims of mastery.

## Internal usability audit — 29 October 2026

This was an automated and visual desktop review, separate from the learner
sessions above. No learner sessions have been conducted.

The review found overlapping content at 360×320, a very small board at 360×600
with extra-large text, insufficient feedback space under two longer questions,
faint secondary labels, and coordinate labels touching the status area. The
update sets a supported 360×720 narrow / 720×600 wide minimum, prioritizes the
board over the compact top portrait, increases reading space and secondary text
contrast, and fits coordinates within their frame.

Run `python -m scripts.audit_usability` to reproduce the layout and interaction
scan with isolated progress. See [the update report](development/update-2026-10-29.md)
for coverage, verification and the remaining device/accessibility limits.
Use the existing observation template to check whether these changes help real
learners; internal review does not establish teaching effectiveness.
