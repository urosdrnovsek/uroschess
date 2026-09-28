"""Repeat-win ledger, cautious migration, and medal presentation contracts."""

import os
import sqlite3

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pytest

from chess_game.challenge import ChallengeStore, medal_summary
from chess_game.moves import legal_moves
from chess_game.pieces import WHITE, BLACK
from chess_game.study.progress import ProgressStore, ProgressStoreError, SCHEMA_VERSION


def _move(board, uci):
    return next(move for move in legal_moves(board) if str(move) == uci)


def _pippa_win(store):
    session = store.start(WHITE, "pippa-pomeranian")
    for uci in ("e2e4", "f7f6", "d2d4", "g7g5", "d1h5"):
        actor = session.board.side_to_move
        chosen = _move(session.board, uci)
        if actor != session.color:
            session.authorize_search_move(chosen)
        session.accept(chosen, actor)
    assert session.status == "checkmate"
    return session


def _unlock_pippa(store):
    seed = store.start(WHITE)
    store.discard(seed.match_id)
    with store.connection:
        store.connection.executemany(
            "INSERT INTO challenge_victories VALUES ('chicky', ?, ?, 'seed')",
            ((WHITE, seed.match_id), (BLACK, seed.match_id)))


@pytest.mark.parametrize("count,small,gold,label", [
    (0, 0, False, "No medals yet"),
    (1, 1, False, "1 medal"),
    (9, 9, False, "9 medals"),
    (10, 0, True, "Gold medal · 10 lifetime wins"),
    (11, 0, True, "Gold medal · 11 lifetime wins"),
])
def test_medal_summary(count, small, gold, label):
    summary = medal_summary(count)
    assert (summary.small_portraits, summary.gold_portrait, summary.label) == (
        small, gold, label)


def test_rematch_adds_medal_without_regranting_badge(tmp_path):
    with ProgressStore(tmp_path / "progress.sqlite3") as progress:
        store = ChallengeStore(progress)
        _unlock_pippa(store)
        first = _pippa_win(store)
        assert store.reward_for_match(first.match_id) == {
            "medal": True, "new_badge": True}
        second = _pippa_win(store)
        assert store.reward_for_match(second.match_id) == {
            "medal": True, "new_badge": False}
        assert store.medal_counts()["pippa-pomeranian"] == 2
        assert progress.connection.execute(
            "SELECT COUNT(*) FROM challenge_victories "
            "WHERE opponent_id='pippa-pomeranian' AND human_color='w'").fetchone()[0] == 1
        with pytest.raises(ValueError):
            store._save(second, "checkmate")
        assert store.medal_counts()["pippa-pomeranian"] == 2


def test_resumed_win_counts_once_and_other_endings_do_not(tmp_path):
    with ProgressStore(tmp_path / "progress.sqlite3") as progress:
        store = ChallengeStore(progress)
        _unlock_pippa(store)
        abandoned = store.start(WHITE, "pippa-pomeranian")
        store.discard(abandoned.match_id)
        resigned = store.start(WHITE, "pippa-pomeranian")
        resigned.resign()
        lost = store.start(WHITE, "pippa-pomeranian")
        for uci in ("f2f3", "e7e5", "g2g4", "d8h4"):
            actor = lost.board.side_to_move
            chosen = _move(lost.board, uci)
            if actor != lost.color:
                lost.authorize_search_move(chosen)
            lost.accept(chosen, actor)
        assert lost.status == "checkmate"
        assert store.medal_counts()["pippa-pomeranian"] == 0
        session = store.start(WHITE, "pippa-pomeranian")
        session.accept(_move(session.board, "e2e4"), WHITE)
        resumed = store.resume()
        for uci in ("f7f6", "d2d4", "g7g5", "d1h5"):
            actor = resumed.board.side_to_move
            chosen = _move(resumed.board, uci)
            if actor != resumed.color:
                resumed.authorize_search_move(chosen)
            resumed.accept(chosen, actor)
        assert resumed.status == "checkmate"
        assert store.medal_counts()["pippa-pomeranian"] == 1
        assert store.reward_for_match(resumed.match_id)["medal"]


def test_medal_insert_failure_rolls_back_terminal_match_and_badge(tmp_path):
    with ProgressStore(tmp_path / "progress.sqlite3") as progress:
        store = ChallengeStore(progress)
        _unlock_pippa(store)
        session = store.start(WHITE, "pippa-pomeranian")
        for uci in ("e2e4", "f7f6", "d2d4", "g7g5"):
            actor = session.board.side_to_move
            chosen = _move(session.board, uci)
            if actor != session.color:
                session.authorize_search_move(chosen)
            session.accept(chosen, actor)
        with progress.connection:
            progress.connection.execute(
                """CREATE TRIGGER reject_medal BEFORE INSERT ON challenge_win_events
                   BEGIN SELECT RAISE(ABORT, 'medal failed'); END""")
        with pytest.raises(sqlite3.IntegrityError, match="medal failed"):
            session.accept(_move(session.board, "d1h5"), WHITE)
        assert session.status == "ongoing"
        assert store.active()["result"] is None
        assert store.medal_counts()["pippa-pomeranian"] == 0
        assert ("pippa-pomeranian", WHITE) not in store.victories()


def test_upgrade_backfills_only_verified_retained_wins(tmp_path):
    path = tmp_path / "progress.sqlite3"
    with ProgressStore(path) as progress:
        store = ChallengeStore(progress)
        _unlock_pippa(store)
        valid = _pippa_win(store)
        with progress.connection:
            progress.connection.execute(
                """INSERT INTO challenge_matches
                   SELECT 'invalid-copy', opponent_id, human_color,
                          policy_revision, state, moves_json, 'wrong fen',
                          move_seed, comment_seed, comment_id, result, updated_at
                   FROM challenge_matches WHERE match_id = ?""",
                (valid.match_id,))
            progress.connection.execute(
                """INSERT INTO challenge_policies
                   SELECT 'invalid-copy', parameters_json FROM challenge_policies
                   WHERE match_id = ?""", (valid.match_id,))
            progress.connection.execute("DROP TABLE challenge_win_events")
            progress.connection.execute("UPDATE schema_info SET version = 9")
    with ProgressStore(path) as upgraded:
        store = ChallengeStore(upgraded)
        assert upgraded.connection.execute(
            "SELECT version FROM schema_info").fetchone()[0] == SCHEMA_VERSION
        assert store.medal_counts()["pippa-pomeranian"] == 1
        assert store.reward_for_match(valid.match_id)["medal"]
        assert store.reward_for_match("invalid-copy") is None
        assert ("pippa-pomeranian", WHITE) in store.victories()


def test_upgrade_failure_rolls_back_events_and_version(tmp_path):
    path = tmp_path / "progress.sqlite3"
    with ProgressStore(path) as progress:
        with progress.connection:
            progress.connection.execute("DROP TABLE challenge_win_events")
            progress.connection.execute("UPDATE schema_info SET version = 9")
            progress.connection.execute(
                """CREATE TRIGGER reject_version BEFORE UPDATE ON schema_info
                   BEGIN SELECT RAISE(ABORT, 'migration failed'); END""")
    with pytest.raises(ProgressStoreError, match="migration failed"):
        ProgressStore(path)
    connection = sqlite3.connect(str(path))
    try:
        assert connection.execute("SELECT version FROM schema_info").fetchone()[0] == 9
        assert connection.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE name='challenge_win_events'").fetchone()[0] == 0
    finally:
        connection.close()


def test_result_snapshot_shows_new_badge_then_rematch_medal(tmp_path):
    import pygame
    from chess_game.ui import ChessUI

    ui = ChessUI(tmp_path / "progress.sqlite3")
    try:
        _unlock_pippa(ui.challenge_store)
        for expected_count, expected_badge in ((1, True), (2, False)):
            session = _pippa_win(ui.challenge_store)
            ui.challenge = session
            ui.board = session.board
            ui.status = session.status
            ui._refresh_challenge_progress()
            ui._show_challenge_result()
            snapshot = ui.challenge_progress_snapshot
            assert snapshot["reward"] == {
                "medal": True, "new_badge": expected_badge}
            assert snapshot["counts"]["pippa-pomeranian"] == expected_count
            assert snapshot["states"][1] == "black_required"
            ui._build_menu_buttons()
            assert ui.menu_view == "challenge_result"
            ui._draw_menu()
    finally:
        ui.progress_store.close()
        pygame.quit()


def test_collection_and_master_acknowledgement_ui(tmp_path):
    import pygame
    from chess_game.ui import ChessUI

    ui = ChessUI(tmp_path / "progress.sqlite3")
    try:
        for width, height in ((360, 320), (360, 400), (360, 600),
                              (600, 600), (980, 760)):
            ui.win_w, ui.win_h = width, height
            ui._layout()
            ui._ensure_fonts()
            ui._open_menu_section("main")
            ui._build_menu_buttons()
            collection = next(button for button in ui._menu_buttons
                              if button.label == "Medal collection")
            exit_button = next(button for button in ui._menu_buttons
                               if button.label == "Exit")
            assert collection.rect.top >= exit_button.rect.bottom
            assert collection.rect.bottom <= height
            ui._draw_menu()
            ui._open_collection()
            ui._build_menu_buttons()
            assert ui.menu_view == "collection"
            assert all(button.rect.bottom <= height for button in
                       ui._menu_buttons + ui._collection_cards)
            ui._draw_menu()
            ui.collection_counts.update({
                "chicky": 1, "pippa-pomeranian": 9,
                "tina-turtle": 10, "tom-rabbit": 11})
            ui._draw_menu()
            while True:
                ui._build_menu_buttons()
                ui._draw_menu()
                if not any(button.label == "More medals ›"
                           for button in ui._menu_buttons):
                    break
                ui._change_collection_page(1)
            assert any(button.label.startswith("Monty · ")
                       for button in ui._collection_cards)
            ui.collection_page = 0
        seed = ui.challenge_store.start(WHITE)
        ui.challenge_store.discard(seed.match_id)
        ui.win_w, ui.win_h = 360, 320
        ui.screen = pygame.display.set_mode((360, 320))
        ui._layout()
        ui._ensure_fonts()
        ui.challenge = seed
        ui.status = "resignation"
        ui.challenge_progress_snapshot = {
            "states": ui.challenge_store.stages(),
            "counts": ui.collection_counts, "reward": None, "award": None}
        ui._show_challenge_result()
        ui._build_menu_buttons()
        assert all(button.rect.bottom <= 320 for button in ui._menu_buttons)
        ui._draw_menu()
        ui.challenge = None
        with ui.progress_store.connection:
            ui.progress_store.connection.execute(
                "INSERT INTO challenge_awards VALUES "
                "('uroschess-master', 'now', ?, NULL)", (seed.match_id,))
        ui._open_challenge_menu()
        assert ui.menu_view == "master_award"
        ui._to_menu()
        assert ui.challenge_store.award()["celebration_seen_at"] is None
        ui._open_challenge_menu()
        ui._acknowledge_master()
        assert ui.challenge_store.award()["celebration_seen_at"] is not None
        assert ui.menu_view == "challenge"
    finally:
        ui.progress_store.close()
        pygame.quit()
