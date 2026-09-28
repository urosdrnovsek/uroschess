# Opponent calibration and repeat-win rewards

`scripts/calibrate_opponents.py` runs adjacent challenge policies on the start,
tactical, and endgame FENs documented in the script. Each selected seed is
played with the stronger opponent as White and as Black. The board is created
in memory; no custom-position game enters challenge progress or reward storage.
The JSON export includes the policy revision and parameters, FENs, seeds,
runtime and hardware, each move's elapsed time and deepest completed search
iteration, W/D/L, search failures, and games stopped by the ply cap. Only
finished games enter W/D/L. Wall-clock limits mean a seed does not guarantee
identical search decisions across machines.

Run a full comparison outside the UI and unit tests with:

```bash
.venv/bin/python scripts/calibrate_opponents.py --max-plies 160 \
  --output /tmp/uroschess-calibration.json
```

The initial diagnostic on 28 September 2026 used all six adjacent pairs,
both colours, seed 11, all three FENs, and a four-ply cap. Its exact command
and machine observations are reproducible from
[`calibration-diagnostic.json`](calibration-diagnostic.json). Of 36 games, 35
were truncated. Tina won one tactical-position game as Black against Pippa;
that position starts with a queen against a rook and is not a balanced estimate
of match strength. There were no search failures or zero-depth searches.
Median completed depth across search moves ranged from 1 for early pairs to 7
for Olivia/Monty. These are move-search measurements, not evidence of match
strength. With at most one finished game per pair, win-rate uncertainty is too
large for an ordering or Elo conclusion. Pippa, Bruno, and Olivia retain their
current settings; Monty remains at six seconds and depth 64. A longer batch is
needed before any strength tuning.

```bash
.venv/bin/python scripts/calibrate_opponents.py \
  --positions start,tactical,endgame --seeds 11 --max-plies 4 \
  --output docs/development/calibration-diagnostic.json
```

Schema 10 and the medal UI are described in [ADR 0003](../architecture/0003-challenge-win-events.md).
The result card reports this match's medal and whether its colour badge is
new, plus the next unlocked opponent. In Collection, each character has a
ten-circle row: each win fills one circular portrait; at ten wins the row is
replaced by one larger gold portrait circle, while the lifetime count keeps
increasing. The main menu shelf displays the same medal row, with arrows to
switch characters; after a win it selects that character automatically. Its
Collection button opens the corresponding collection page.
The Master title is durable and its celebration is acknowledged only by an
explicit action.
