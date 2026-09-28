"""Offline, colour-balanced diagnostics for adjacent challenge opponents.

Custom FEN games are isolated in memory and never enter ChallengeStore.
This is a small-sample diagnostic, not an Elo estimator.
"""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import random
import statistics
import sys
import time

from chess_game import ai
from chess_game.board import Board
from chess_game.challenge import OPPONENTS, ROSTER
from chess_game.moves import game_status, legal_moves
from chess_game.notation import from_fen, to_fen
from chess_game.pieces import WHITE, BLACK


POSITIONS = {
    "start": to_fen(Board()),
    "tactical": "4k3/8/8/8/8/8/4q3/4R2K w - - 0 1",
    "endgame": "4k3/6p1/8/8/8/8/1P6/4K3 w - - 0 1",
}
ADJACENT = tuple((left.ident, right.ident)
                 for left, right in zip(ROSTER, ROSTER[1:]))


def choose_move(board, opponent, seed, ply):
    options = legal_moves(board)
    if opponent.preset is None:
        return random.Random("{}:{}".format(seed, ply)).choice(options), {
            "source": "random", "seconds": 0.0, "completed_depth": 0,
            "nodes": 0}
    rng = random.Random("{}:{}:random".format(seed, ply))
    if (opponent.random_move_chance and
            rng.random() < opponent.random_move_chance):
        return rng.choice(options), {
            "source": "policy_random", "seconds": 0.0,
            "completed_depth": 0, "nodes": 0}
    policy = opponent.policy_parameters
    completed = []
    start = time.monotonic()
    # A timed search may unwind through an unfinished branch. Keep the game
    # board separate from the disposable search board, as the UI does.
    move, _score, _pv, nodes = ai.analyse(
        board.clone(), time_limit=policy["seconds"], max_depth=policy["depth"],
        on_progress=lambda depth, score, pv, count: completed.append(depth))
    elapsed = time.monotonic() - start
    if move not in options:
        raise RuntimeError("Search returned no legal move")
    return move, {"source": "search", "seconds": round(elapsed, 4),
                  "completed_depth": max(completed, default=0),
                  "nodes": nodes}


def play_game(weaker, stronger, stronger_color, position, seed, max_plies):
    board = from_fen(POSITIONS[position])
    observations = []
    failure = None
    for ply in range(max_plies):
        if game_status(board) != "ongoing":
            break
        opponent = stronger if board.side_to_move == stronger_color else weaker
        try:
            move, search = choose_move(board, opponent, seed, ply)
        except Exception as error:
            failure = "{}: {}".format(type(error).__name__, error)
            break
        observations.append({"ply": ply, "opponent": opponent.ident,
                             "move": str(move), **search})
        board.make_move(move)
    status = game_status(board)
    if failure:
        outcome = "search_failure"
    elif status == "ongoing":
        outcome = "truncated"
    elif status == "checkmate":
        outcome = ("win" if board.side_to_move != stronger_color else "loss")
    else:
        outcome = "draw"
    return {"weaker": weaker.ident, "stronger": stronger.ident,
            "stronger_color": stronger_color, "position": position,
            "seed": seed, "max_plies": max_plies, "plies": len(observations),
            "status": status, "outcome": outcome, "failure": failure,
            "final_fen": to_fen(board), "moves": observations}


def build_report(pairs, positions, seeds, max_plies):
    games = []
    started = time.monotonic()
    for weaker_id, stronger_id in pairs:
        weaker, stronger = OPPONENTS[weaker_id], OPPONENTS[stronger_id]
        for position in positions:
            for seed in seeds:
                for color in (WHITE, BLACK):
                    games.append(play_game(weaker, stronger, color, position,
                                           seed, max_plies))
    summaries = []
    for weaker_id, stronger_id in pairs:
        subset = [game for game in games if game["weaker"] == weaker_id]
        times = [move["seconds"] for game in subset for move in game["moves"]
                 if move["source"] == "search"]
        depths = [move["completed_depth"] for game in subset
                  for move in game["moves"] if move["source"] == "search"]
        summaries.append({
            "pair": [weaker_id, stronger_id],
            "by_color": {color: {outcome: sum(
                game["stronger_color"] == color and game["outcome"] == outcome
                for game in subset)
                for outcome in ("win", "draw", "loss", "truncated",
                                "search_failure")}
                for color in (WHITE, BLACK)},
            "median_search_seconds": (statistics.median(times) if times else None),
            "median_completed_depth": (statistics.median(depths)
                                       if depths else None),
            "searches_without_completed_depth": sum(depth == 0 for depth in depths),
        })
    return {
        "format": "uroschess-opponent-calibration-1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "runtime": {"python": platform.python_version(),
                    "platform": platform.platform(),
                    "processor": platform.processor(),
                    "cpu_count": os.cpu_count(),
                    "elapsed_seconds": round(time.monotonic() - started, 3)},
        "method": ("Adjacent opponents play each selected position in both "
                   "colour assignments with each seed. Only finished games "
                   "enter W/D/L; truncations and search failures are separate. "
                   "Small samples and time-dependent search prevent an Elo or "
                   "reliable strength claim."),
        "positions": {name: POSITIONS[name] for name in positions},
        "seeds": seeds, "max_plies": max_plies,
        "policies": {ident: OPPONENTS[ident].policy_parameters
                     for pair in pairs for ident in pair},
        "summaries": summaries, "games": games,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pairs", default=",".join(":".join(p) for p in ADJACENT),
                        help="comma-separated adjacent weaker:stronger IDs")
    parser.add_argument("--positions", default="start,tactical,endgame")
    parser.add_argument("--seeds", default="11,29,47")
    parser.add_argument("--max-plies", type=int, default=160)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    pairs = [tuple(pair.split(":")) for pair in args.pairs.split(",")]
    positions = args.positions.split(",")
    try:
        seeds = [int(seed) for seed in args.seeds.split(",")]
        if (not pairs or any(pair not in ADJACENT for pair in pairs) or
                not positions or any(position not in POSITIONS for position in positions)
                or not seeds or args.max_plies < 1):
            raise ValueError("Invalid pair, position, seed, or max-plies")
    except ValueError as error:
        parser.error(str(error))
    report = build_report(pairs, positions, seeds, args.max_plies)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("Wrote {} games to {}".format(len(report["games"]), args.output))
    for summary in report["summaries"]:
        print("{} → {}: {}".format(*summary["pair"], summary["by_color"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
