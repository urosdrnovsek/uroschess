"""Window geometry for board, status, and study panels."""

import pygame


def layout_board(ui):
    P, GAP, SGAP, SH = 16, 14, 12, 42
    ui.pad, ui.status_h = P, SH
    ui._board_thought_rect = None
    medium_side = (ui.scene in ("lesson", "replay")
                   and 560 <= ui.win_w < 820 and ui.win_h <= 640)
    lesson_narrow = (ui.scene in ("lesson", "replay")
                     and ui.win_w < 820 and not medium_side)
    ui.show_panel = ui.win_w >= 720 or ui.scene in ("lesson", "replay")
    ui._portrait_in_panel = (
        ui.show_panel and ui.win_h >= 620 and not medium_side
        and (ui.scene in ("game", "replay")
             or ui.scene == "lesson" and not lesson_narrow))
    if lesson_narrow:
        panel_w = ui.win_w - 2 * P
        ui.panel_w = panel_w
        text_room = int(max(0, ui.text_scale - 1.0) * 140)
        ui.panel_h = max(220, min(300 + text_room,
                                  ui.win_h * 55 // 100))
        ui.panel_x = P
        ui.panel_y = ui.win_h - P - ui.panel_h
        inner_w = ui.win_w - 2 * P
        thought_space = 98 - min(6, text_room // 9)
        ui._board_thought_rect = pygame.Rect(
            P, P, inner_w, thought_space - 24)
        inner_h = max(96, ui.panel_y - P - SH - SGAP - GAP
                      - thought_space)
        board = max(96, min(inner_w, inner_h))
        sq = max(12, board // 8)
        ui.SQ = sq
        ui.board_px = sq * 8
        ui.frame = max(5, sq // 5)
        ui.board_x = P + max(0, (inner_w - ui.board_px) // 2)
        ui.board_y = (P + thought_space
                        + max(0, (inner_h - ui.board_px) // 2))
        ui.status_x = P
        ui.status_y = ui.panel_y - SH - SGAP
        ui.status_w = inner_w
        return
    panel_w = ((250 if medium_side else
                360 if ui.scene == "lesson" else 320)
               if ui.scene in ("replay", "lesson") else 250)
    panel_w = panel_w if ui.show_panel else 0
    inner_w = ui.win_w - 2 * P - (panel_w + GAP if ui.show_panel else 0)
    board_portrait = (ui.scene == "lesson" and not ui._portrait_in_panel
                      or ui.scene == "replay" and not ui._portrait_in_panel
                      or ui.scene == "game" and not ui._portrait_in_panel)
    thought_space = 122 if board_portrait else 0
    inner_h = ui.win_h - 2 * P - SH - SGAP - thought_space

    board = max(224, min(inner_w, inner_h))
    sq = max(28, board // 8)
    frame = max(7, sq // 5)
    board = max(224, min(inner_w - 2 * frame, inner_h - 2 * frame))
    sq = max(28, board // 8)
    ui.SQ = sq
    ui.board_px = sq * 8
    ui.frame = max(7, sq // 5)

    ui.board_x = P + ui.frame + max(
        0, (inner_w - ui.board_px - 2 * ui.frame) // 2)
    ui.board_y = P + thought_space + ui.frame + max(
        0, (inner_h - ui.board_px - 2 * ui.frame) // 2)
    ui.status_x = ui.board_x - ui.frame
    ui.status_y = ui.board_y + ui.board_px + ui.frame + SGAP
    ui.status_w = ui.board_px + 2 * ui.frame
    if board_portrait:
        ui._board_thought_rect = pygame.Rect(
            ui.status_x, P, ui.status_w, thought_space - 24)
    ui.panel_w = panel_w
    ui.panel_x = P + inner_w + GAP
    ui.panel_y = P
    ui.panel_h = ui.win_h - 2 * P
