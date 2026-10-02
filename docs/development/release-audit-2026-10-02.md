# Release audit — 2 October 2026

This audit covers the current working tree, including the one-page Medals view
and the search timeout fallback. It is not a tagged release.

## Checks completed

- Reviewed home, Medals, Play, challenge, Learn, lesson, replay, and ordinary
  game screens with headless Pygame input at 360×320, 360×600, 420×720,
  600×600, and 980×760, including extra-large text. All seven medal cards and
  the return action fit on one page at the smallest size. Narrow ordinary game
  controls and challenge save/resume were exercised.
- Built a wheel without downloading dependencies, installed it into a temporary
  target outside the checkout, and launched it with the existing Python 3.14.7
  and Pygame 2.6.1 runtime. It loaded 31 games, 31 lessons, nine courses, and
  all seven BMP portraits offline. Medals, a lesson, replay, a narrow game,
  and challenge save/resume worked from the installed package.
- The full suite passed 160 tests on Python 3.14.7. Content validation,
  rendering smoke, and `git diff --check` also passed. Pygame emitted its
  existing AVX2 build warning.
- The [80-ply calibration sample](calibration-2026-10-02.json) played 12 games
  for three adjacent opponent pairs on start and endgame positions in both
  colours. It produced three stronger-side wins, three draws, six truncations,
  and zero search failures after the engine timeout fix. No strength tuning was
  made from this small sample.
- Package metadata and the README now state Python 3.9 as the minimum, matching
  the oldest version configured in CI. Python 3.9 was not available locally.

## Remaining release evidence

- Observe new learners using the lessons and challenge without guidance.
- Test a fresh Pygame dependency install and the advertised platforms outside
  this existing Linux runtime.
- Run more complete, colour-balanced games across the full opponent ladder
  before claiming that difficulty increases consistently.
