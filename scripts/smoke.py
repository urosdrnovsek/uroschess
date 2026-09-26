"""Headless smoke test: exercise the engine and render the UI once."""
import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
from chess_game.ui import ChessUI
from chess_game.board import Board
from chess_game import ai
from chess_game.moves import legal_moves, game_status
from chess_game.pieces import WHITE, BLACK


def mv(b, s):
    frm = (8 - int(s[1]), "abcdefgh".index(s[0]))
    to = (8 - int(s[3]), "abcdefgh".index(s[2]))
    return next(x for x in legal_moves(b) if x.frm == frm and x.to == to
               and (not x.promo or x.promo == "q"))


# --- AI finds Fool's mate ---
b = Board()
for s in ["f2f3", "e7e5", "g2g4"]:
    b.make_move(mv(b, s))
best = ai.best_move(b, time_limit=1.0)
b.make_move(best)
print("AI reply to pre-mate position:", best, "-> status:", game_status(b))
assert game_status(b) == "checkmate", "AI should find Qh4#"

# --- UI render + screenshot ---
ui = ChessUI(":memory:")
ui.start_game({WHITE})
print("glyph font in use:", ui.use_glyphs)
ui._select((6, 4))
ui._apply(next(m for m in ui.legal_from_selected if m.to == (4, 4)))
while ui.thinking:
    ui._poll_ai()
ui._build_game_buttons()
ui._draw()
out = "scripts/board.bmp"
flat = pygame.Surface(ui.screen.get_size())
flat.blit(ui.screen, (0, 0))
pygame.image.save(flat, out)
print("saved", out, "| moves:", " ".join(ui.sans), "| status:", ui.status)
ui.progress_store.close()
