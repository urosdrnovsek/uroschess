"""pygame front-end: menu, board rendering, drag-and-drop + keyboard input, side
panel (move list / captured pieces / eval bar), and the AI-thread glue.

The look follows the active Omarchy theme (``chess_game.theme.Palette`` reads
``~/.local/state/omarchy/current/theme/colors.toml``): flat theme-coloured chrome,
a single accent, monospace UI type, corner radius matched to the compositor, and
the window left as a plain rectangle so Hyprland owns the frame. The board itself
stays richly textured and lit; four material board styles plus a "Theme" style
derived from the palette are chosen in the Colour-options panel.

The window is resizable. Replay and lesson panels stack under the board in a
narrow window so their controls remain available.
"""

import math
import os
import queue
import random
import threading
import time
import webbrowser

os.environ.setdefault("SDL_VIDEO_X11_WMCLASS", "uroschess")
os.environ.setdefault("SDL_VIDEO_WAYLAND_WMCLASS", "uroschess")

import pygame

from . import ai, sound, theme
from .board import Board
from .chess_thoughts import ChessThought, random_thought
from .moves import legal_moves, in_check, game_status
from . import notation
from .pieces import WHITE, BLACK, GLYPHS, LETTERS, VALUES
from .study import (
    COMPLETED,
    EXPLORING,
    FEEDBACK,
    QUESTION,
    READING,
    ContentLoadError,
    LessonController,
    ProgressStore,
    ProgressStoreError,
    ReplayController,
    SquareHighlight,
    load_game_library,
)
from .study.coaching import coach_advice, coach_thought
from .study.course_progress import build_course_summary
from .views import BoardView, Button, StudyView, draw_focus_ring
from .views.chess_thought_view import draw_chess_thought
from .views.course_about_view import draw_course_about
from .views.player_library_view import draw_player_card
from .views.layout import layout_board
from .menu import (MenuLayoutMixin, DIFFICULTIES, BOARD_STYLE_NAMES,
                   WHITE_PRESETS, BLACK_PRESETS, TEXT_SIZES)

# ------------------------------------------------------------------- static data
# A short route through the starter pack, ordered by the ideas a new player
# needs first. Other lessons remain available from the category libraries.
# material board styles — squares / frame / coords + which texture to paint
MATERIALS = {
    "Wood": {
        "light": (232, 197, 148), "dark": (150, 100, 62),
        "frame": (95, 62, 42), "frame_hi": (132, 92, 62),
        "coord": (240, 226, 205), "grain": True, "texture": "wood",
    },
    "Marble": {
        "light": (236, 236, 239), "dark": (139, 142, 152),
        "frame": (66, 68, 78), "frame_hi": (150, 153, 164),
        "coord": (244, 245, 249), "grain": True, "texture": "marble",
    },
    "Emerald": {
        "light": (238, 238, 210), "dark": (112, 146, 88),
        "frame": (54, 70, 46), "frame_hi": (92, 114, 74),
        "coord": (238, 240, 220), "grain": False, "texture": "emerald",
    },
    "Ocean": {
        "light": (201, 226, 238), "dark": (74, 122, 152),
        "frame": (32, 52, 68), "frame_hi": (70, 104, 132),
        "coord": (226, 240, 248), "grain": False, "texture": "ocean",
    },
}
_UI_FONTS = [
    "JetBrainsMono Nerd Font", "JetBrainsMono NF", "JetBrains Mono",
    "CaskaydiaMono Nerd Font", "Cascadia Mono", "DejaVu Sans Mono",
]
_CHESS_FONT_CANDIDATES = [
    "Noto Sans Symbols 2", "notosanssymbols2", "Symbola", "DejaVu Sans",
    "Segoe UI Symbol", "FreeSerif", "Arial Unicode MS",
]


# ======================================================================= helpers
def _clamp(v):
    return max(0, min(255, int(v)))


def _lighten(c, n):
    return (_clamp(c[0] + n), _clamp(c[1] + n), _clamp(c[2] + n))


def _darken(c, n):
    return _lighten(c, -n)


def _mix(a, b, t):
    return (_clamp(a[0] + (b[0] - a[0]) * t),
            _clamp(a[1] + (b[1] - a[1]) * t),
            _clamp(a[2] + (b[2] - a[2]) * t))


def _luma(c):
    return 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]


def _outline_for(col):
    return (22, 18, 16) if _luma(col) > 120 else (240, 235, 229)


def _text_for(col):
    return (18, 16, 14) if _luma(col) > 120 else (250, 248, 244)


def _ipts(pts):
    return [(int(x), int(y)) for x, y in pts]


def _vgradient(w, h, c1, c2):
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    span = max(1, h - 1)
    for y in range(h):
        t = y / span
        surf.fill((_clamp(c1[0] + (c2[0] - c1[0]) * t),
                   _clamp(c1[1] + (c2[1] - c1[1]) * t),
                   _clamp(c1[2] + (c2[2] - c1[2]) * t), 255), (0, y, w, 1))
    return surf


def _round_rect_alpha(target, rect, rgba, radius):
    rect = pygame.Rect(rect)
    s = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
    pygame.draw.rect(s, rgba, s.get_rect(), border_radius=radius)
    target.blit(s, rect.topleft)


def _draw_shadow(target, rect, radius, layers=6, base_alpha=18, grow=3, dy=6):
    rect = pygame.Rect(rect)
    for i in range(layers, 0, -1):
        pad = i * grow
        s = pygame.Surface((rect.w + pad * 2, rect.h + pad * 2), pygame.SRCALPHA)
        pygame.draw.rect(s, (0, 0, 0, base_alpha), s.get_rect(),
                         border_radius=radius + pad)
        target.blit(s, (rect.x - pad, rect.y - pad + dy))


def _hairline(target, rect, color, radius):
    rect = pygame.Rect(rect)
    ov = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
    pygame.draw.rect(ov, (*color, 255), ov.get_rect(), width=1,
                     border_radius=radius)
    target.blit(ov, rect.topleft)


def _flat_button(target, rect, fill, border, radius=8):
    _round_rect_alpha(target, rect, (*fill, 255), radius)
    _hairline(target, rect, border, radius)


def _edge_vignette(surf, mode, reach=90):
    w, h = surf.get_size()
    col = (30, 20, 35) if mode == "light" else (0, 0, 0)
    a0 = 13 if mode == "light" else 42
    v = pygame.Surface((w, h), pygame.SRCALPHA)
    for d in range(reach):
        a = int(a0 * (1 - d / reach) ** 2.4)
        if a <= 0:
            continue
        c = (*col, a)
        pygame.draw.line(v, c, (0, d), (w, d))
        pygame.draw.line(v, c, (0, h - 1 - d), (w, h - 1 - d))
        pygame.draw.line(v, c, (d, 0), (d, h))
        pygame.draw.line(v, c, (w - 1 - d, 0), (w - 1 - d, h))
    surf.blit(v, (0, 0))


# ---- board texture / lighting -----------------------------------------------
def _radial_field(size, fn, small=72):
    s = pygame.Surface((small, small), pygame.SRCALPHA)
    for yy in range(small):
        for xx in range(small):
            s.set_at((xx, yy), fn(xx / (small - 1), yy / (small - 1)))
    return pygame.transform.smoothscale(s, (size, size))


def _radial_shade(size, edge_alpha=72, power=2.5):
    return _radial_field(size, lambda nx, ny: (
        0, 0, 0, int(edge_alpha * (math.hypot(nx - 0.5, ny - 0.5) / 0.7071) ** power)))


def _radial_glow(size, cx=0.34, cy=0.26, spread=0.95, max_alpha=40):
    return _radial_field(size, lambda nx, ny: (
        255, 255, 255,
        int(max_alpha * max(0.0, 1 - math.hypot(nx - cx, ny - cy) / spread) ** 1.9)))


def _soft_blob(tile, s, cx, cy, rad, rgba):
    b = pygame.Surface((s, s), pygame.SRCALPHA)
    r, g, bl, a = rgba
    for i in range(5, 0, -1):
        pygame.draw.circle(b, (r, g, bl, a // 5), (int(cx), int(cy)),
                           int(rad * i / 5))
    tile.blit(b, (0, 0))


def _corner_sheen(tile, s):
    sh = pygame.Surface((s, s), pygame.SRCALPHA)
    for y in range(s):
        pygame.draw.line(sh, (255, 255, 255, int(15 * (1 - y / s))),
                         (0, y), (s - y, y))
    tile.blit(sh, (0, 0))


def _square_texture(tile, s, base, texture, rng):
    if texture == "wood":
        for _ in range(rng.randint(4, 7)):
            yy = rng.uniform(0, s)
            h = rng.randint(3, 12)
            shade = rng.choice((-1, 1)) * rng.randint(5, 15)
            band = pygame.Surface((s, h), pygame.SRCALPHA)
            band.fill((*_lighten(base, shade), rng.randint(12, 24)))
            tile.blit(band, (0, yy - h / 2))
        if rng.random() < 0.05:
            _soft_blob(tile, s, rng.uniform(s * .3, s * .7),
                       rng.uniform(s * .3, s * .7), rng.uniform(4, 8),
                       (*_darken(base, 24), 26))
    elif texture == "marble":
        for _ in range(4):
            shade = rng.choice((-1, 1)) * rng.randint(6, 16)
            _soft_blob(tile, s, rng.uniform(0, s), rng.uniform(0, s),
                       rng.uniform(s * .35, s * .75), (*_lighten(base, shade), 24))
    elif texture == "emerald":
        for _ in range(3):
            _soft_blob(tile, s, rng.uniform(0, s), rng.uniform(0, s),
                       rng.uniform(s * .4, s * .8),
                       (*_lighten(base, rng.randint(6, 14)), 18))
    elif texture == "ocean":
        for _ in range(rng.randint(3, 5)):
            yy = rng.uniform(0, s)
            h = rng.randint(6, 16)
            shade = rng.choice((-1, 1)) * rng.randint(7, 16)
            band = pygame.Surface((s, h), pygame.SRCALPHA)
            band.fill((*_lighten(base, shade), rng.randint(14, 28)))
            tile.blit(band, (0, yy - h / 2))
    _corner_sheen(tile, s)


def _paint_square(surf, x, y, size, base, texture, rng):
    tile = pygame.Surface((size, size), pygame.SRCALPHA)
    tile.blit(_vgradient(size, size, _lighten(base, 11), _darken(base, 9)), (0, 0))
    _square_texture(tile, size, base, texture, rng)
    ov = pygame.Surface((size, size), pygame.SRCALPHA)
    pygame.draw.line(ov, (255, 255, 255, 18), (0, 0), (size - 1, 0))
    pygame.draw.line(ov, (255, 255, 255, 12), (0, 0), (0, size - 1))
    tile.blit(ov, (0, 0))
    surf.blit(tile, (x, y))


def _paint_board(surf, ox, oy, px, sdef, rng, coord_font=None, flipped=False,
                 frame=0, radius=8):
    sq = px // 8
    if frame:
        fr = pygame.Rect(ox - frame, oy - frame, px + 2 * frame, px + 2 * frame)
        _draw_shadow(surf, fr, radius + 4, layers=9, base_alpha=20, grow=3, dy=10)
        fg = _vgradient(fr.w, fr.h, _lighten(sdef["frame"], 24),
                        _darken(sdef["frame"], 26))
        m = pygame.Surface(fr.size, pygame.SRCALPHA)
        pygame.draw.rect(m, (255, 255, 255, 255), m.get_rect(),
                         border_radius=radius + 4)
        fg.blit(m, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
        if sdef.get("grain"):
            for _ in range(fr.w // 3):
                fx = rng.randint(0, fr.w - 1)
                pygame.draw.line(fg, (*_darken(sdef["frame"], rng.randint(6, 20)),
                                      rng.randint(18, 50)), (fx, 0), (fx, fr.h))
        surf.blit(fg, fr.topleft)
        _hairline(surf, fr, _lighten(sdef["frame_hi"], 8), radius + 4)
        pygame.draw.rect(surf, _darken(sdef["frame"], 50),
                         (ox - 3, oy - 3, px + 6, px + 6), width=3)

    for r in range(8):
        for c in range(8):
            rr, cc = (7 - r, 7 - c) if flipped else (r, c)
            base = sdef["light"] if (rr + cc) % 2 == 0 else sdef["dark"]
            _paint_square(surf, ox + c * sq, oy + r * sq, sq, base,
                          sdef["texture"], rng)

    inner = pygame.Surface((px, px), pygame.SRCALPHA)
    d = max(8, px // 40)
    for i in range(d):
        pygame.draw.rect(inner, (0, 0, 0, int(66 * (1 - i / d) ** 2)),
                         (i, i, px - 2 * i, px - 2 * i), 1)
    surf.blit(inner, (ox, oy))
    surf.blit(_radial_glow(px), (ox, oy))
    surf.blit(_radial_shade(px), (ox, oy))
    gloss = pygame.Surface((px, px), pygame.SRCALPHA)
    for yy in range(px):
        pygame.draw.line(gloss, (255, 255, 255, int(28 * (1 - yy / px) ** 1.7)),
                         (0, yy), (px, yy))
    surf.blit(gloss, (ox, oy))

    if coord_font is not None:
        files = "abcdefgh"
        off = max(9, int(frame * 0.55))
        for i in range(8):
            c = i if not flipped else 7 - i
            fs = coord_font.render(files[c], True, sdef["coord"])
            surf.blit(fs, fs.get_rect(center=(ox + i * sq + sq // 2, oy + px + off)))
            rs = coord_font.render(str(8 - c), True, sdef["coord"])
            surf.blit(rs, rs.get_rect(center=(ox - off, oy + i * sq + sq // 2)))


# ---- fonts -----------------------------------------------------------------
def _renders_glyph(font, glyph):
    missing = font.render("�", True, (0, 0, 0))
    got = font.render(glyph, True, (0, 0, 0))
    if got.get_size() != missing.get_size():
        return True
    return pygame.image.tobytes(got, "RGB") != pygame.image.tobytes(missing, "RGB")


def _load_piece_font(size):
    size = max(12, size)
    for name in _CHESS_FONT_CANDIDATES:
        path = pygame.font.match_font(name)
        if not path:
            continue
        f = pygame.font.Font(path, size)
        if all(_renders_glyph(f, g) for g in GLYPHS.values()):
            return f, True
    return pygame.font.SysFont("dejavusans", int(size * 0.66), bold=True), False


def _ui_font(size, bold=False):
    for name in _UI_FONTS:
        path = pygame.font.match_font(name, bold=bold)
        if path:
            return pygame.font.Font(path, size)
    return pygame.font.SysFont("monospace", size, bold=bold)


def _wrap_text(font, text, max_width):
    """Wrap text to pixel width while retaining authored paragraph breaks."""
    lines = []
    for paragraph in (text or "").splitlines() or [""]:
        words = paragraph.split()
        if not words:
            lines.append("")
            continue
        current = words[0]
        for word in words[1:]:
            candidate = current + " " + word
            if font.size(candidate)[0] <= max_width:
                current = candidate
            else:
                lines.append(current)
                current = word
        lines.append(current)
    return lines


def _fit_text(font, text, max_width):
    """Keep a single line inside its control, with an ellipsis if needed."""
    if font.size(text)[0] <= max_width:
        return text
    text = text.rstrip("…")
    while text and font.size(text + "…")[0] > max_width:
        text = text[:-1]
    return text.rstrip() + "…"


class ChessUI(MenuLayoutMixin):
    def __init__(self, user_data_path=None):
        pygame.init()
        pygame.display.set_caption("Uroschess")
        self.pal = theme.Palette()
        self._theme_mtime = theme.colors_mtime()

        self._flags = pygame.RESIZABLE
        self._last_resize = (980, 760)
        self.screen = pygame.display.set_mode(self._last_resize, self._flags)
        self.win_w, self.win_h = self._last_resize
        self.clock = pygame.time.Clock()
        sound.init()
        self.chess_thought = random_thought()
        self._thought_previous = None
        self._thought_changed_at = 0.0
        self._thought_duration = 0.48
        self._portrait_hit_rect = None

        self.text_scale = 1.0
        self._rebuild_ui_fonts()

        self.running = True
        self._dirty = True
        self._hover = None
        self._button_focus = None
        self.scene = "menu"
        self.menu_view = "main"
        self.library_filter = "guided_game"
        self.library_return = "main"
        self.library_page = 0
        self.course_page = 0
        self.last_learn_browse = None
        self.replay_return = None
        self.active_course_id = None
        self.lesson_course_id = None
        self.lesson_return_view = "library"
        self.coach_profile = None
        self.board_style = "Theme"
        self.white_col = WHITE_PRESETS[0]
        self.black_col = BLACK_PRESETS[0]
        self.difficulty = 1
        self.flipped = False
        self.cursor = None
        self.toast = ""
        self.toast_until = 0.0
        self._menu_buttons = []
        self._game_buttons = []
        self._promo_buttons = []
        self._menu_heads = []
        self._game_bg = None
        self._game_bg_key = None
        self._menu_bg = None
        self._menu_bg_key = None
        self._preview = None
        self._preview_key = None
        self._piece_size = None
        self.board_view = None
        self.study_view = None
        self.replay = None
        self.replay_entry = None
        self.replay_autoplay = False
        self.replay_speeds = (0.6, 1.0, 1.6, 2.4)
        self.replay_speed_index = 1
        self.sound_enabled = True
        self.move_hint_seen = False
        self.replay_next_at = 0.0
        self.replay_mainline = ()
        self.replay_variations = ()
        self._replay_move_hits = []
        self.replay_scroll = 0
        self.replay_max_scroll = 0
        self.replay_visible_rows = 1
        self.replay_scroll_manual = False
        self.lesson = None
        self.lesson_entry = None
        self.lesson_scroll = 0
        self.lesson_max_scroll = 0
        self.lesson_message = ""
        self.progress_store = None
        self._course_summary_cache = {}
        self.progress_error = ""
        self.preferences_error = ""
        try:
            self.progress_store = ProgressStore(user_data_path)
        except ProgressStoreError as error:
            self.progress_error = str(error)
        if self.progress_store is not None:
            try:
                self._apply_saved_preferences(
                    self.progress_store.load_settings())
            except ProgressStoreError as error:
                self.preferences_error = str(error)
        sound.set_enabled(self.sound_enabled)
        try:
            self.game_library = load_game_library()
            self.library_errors = self.game_library.errors
        except ContentLoadError as error:
            self.game_library = None
            self.library_errors = (str(error),)

        self._layout()
        self._ensure_fonts()
        self._new_game(human_colors={WHITE})

    # ------------------------------------------------------------- theme/layout
    def _rebuild_ui_fonts(self):
        scaled = lambda size: max(8, round(size * self.text_scale))
        self.title_font = _ui_font(scaled(38), bold=True)
        self.status_font = _ui_font(scaled(17), bold=True)
        self.text_font = _ui_font(scaled(16))
        self.small_font = _ui_font(scaled(13))
        self.mono_font = _ui_font(scaled(13))
        self.tag_font = _ui_font(scaled(11), bold=True)
        self.coord_font = _ui_font(scaled(11), bold=True)

    def _apply_saved_preferences(self, settings):
        scales = {value for _label, value in TEXT_SIZES}
        scale = settings.get("text_scale", self.text_scale)
        if isinstance(scale, (int, float)) and float(scale) in scales:
            self.text_scale = float(scale)
            self._rebuild_ui_fonts()
        style = settings.get("board_style", self.board_style)
        if style in BOARD_STYLE_NAMES:
            self.board_style = style
        white = settings.get("white_color", self.white_col)
        if isinstance(white, (list, tuple)) and tuple(white) in WHITE_PRESETS:
            self.white_col = tuple(white)
        black = settings.get("black_color", self.black_col)
        if isinstance(black, (list, tuple)) and tuple(black) in BLACK_PRESETS:
            self.black_col = tuple(black)
        difficulty = settings.get("difficulty", self.difficulty)
        if isinstance(difficulty, int) and 0 <= difficulty < len(DIFFICULTIES):
            self.difficulty = difficulty
        speed = settings.get("replay_speed_index", self.replay_speed_index)
        if isinstance(speed, int) and 0 <= speed < len(self.replay_speeds):
            self.replay_speed_index = speed
        enabled = settings.get("sound_enabled", self.sound_enabled)
        if isinstance(enabled, bool):
            self.sound_enabled = enabled
        self.move_hint_seen = bool(settings.get("move_hint_seen", False))
        self.active_course_id = settings.get("last_course_id")
        browse = settings.get("last_learn_browse")
        if isinstance(browse, dict):
            self.last_learn_browse = browse

    def _save_preferences(self, **settings):
        if self.progress_store is None:
            return
        try:
            self.progress_store.save_settings(settings)
            self.preferences_error = ""
        except ProgressStoreError as error:
            self.preferences_error = str(error)

    def _reload_theme(self):
        self.pal = theme.Palette()
        self._theme_mtime = theme.colors_mtime()
        self._game_bg = self._menu_bg = self._preview = None
        self._dirty = True

    def _maybe_reload_theme(self):
        mt = theme.colors_mtime()
        if mt != self._theme_mtime:
            self._reload_theme()

    def _change_chess_thought(self, play_sound=True):
        if self.scene == "lesson" and self.coach_profile is not None:
            self._repeat_coach_advice()
            return
        self._thought_previous = self.chess_thought
        self.chess_thought = random_thought(exclude=self.chess_thought)
        self._thought_changed_at = time.monotonic()
        if play_sound:
            sound.play("click")
        self._dirty = True

    def _thought_progress(self):
        if self._thought_previous is None:
            return 1.0
        progress = min(1.0, (time.monotonic() - self._thought_changed_at)
                       / self._thought_duration)
        if progress >= 1.0:
            self._thought_previous = None
        return progress

    def _layout(self):
        layout_board(self)

    def _ensure_fonts(self):
        size = int(self.SQ * 0.82)
        if self._piece_size != size:
            self.piece_font, self.use_glyphs = _load_piece_font(size)
            self.small_piece_font, _ = _load_piece_font(max(14, self.SQ // 4))
            self._piece_size = size
        self._sync_board_view()

    def _sync_board_view(self):
        if self.board_view is None:
            self.board_view = BoardView(
                self.screen, self.board_x, self.board_y, self.SQ,
                self.piece_font, self.small_font,
                use_glyphs=self.use_glyphs, flipped=self.flipped)
            return
        self.board_view.configure(
            self.screen, self.board_x, self.board_y, self.SQ,
            self.piece_font, self.small_font,
            use_glyphs=self.use_glyphs, flipped=self.flipped)

    def _sync_study_view(self):
        if self.study_view is None:
            self.study_view = StudyView(
                self.screen, self.pal, self.status_font, self.text_font,
                self.small_font, self.mono_font, self.tag_font)
            return
        self.study_view.configure(
            self.screen, self.pal, self.status_font, self.text_font,
            self.small_font, self.mono_font, self.tag_font)

    def _on_resize(self, w, h):
        w, h = max(360, w), max(320, h)
        # Compare against the last size we were *asked* for, not screen.get_size()
        # — on Wayland SDL reports the frame size back but keeps sending the
        # (smaller) content size, which otherwise loops forever.
        if (w, h) == self._last_resize:
            return False
        self._last_resize = (w, h)
        self.screen = pygame.display.set_mode((w, h), self._flags)
        self.win_w, self.win_h = w, h
        self._layout()
        self._ensure_fonts()
        self._game_bg = self._menu_bg = self._preview = None
        self._menu_buttons = []
        self._portrait_hit_rect = None
        return True

    def _style_def(self, name):
        if name == "Theme":
            p = self.pal
            return {"light": p.sq_light, "dark": p.sq_dark, "frame": p.frame,
                    "frame_hi": p.frame_hi, "coord": p.coord, "grain": False,
                    "texture": "flat"}
        return MATERIALS[name]

    # ================================================================= setup
    def _new_game(self, human_colors):
        self.human_colors = human_colors
        self.board = Board()
        self.moves = []
        self.sans = []
        self.selected = None
        self.legal_from_selected = []
        self.last_move = None
        self.status = "ongoing"
        self.dragging = None
        self.drag_pos = (0, 0)
        self.drag_started = False
        self.pending_promo = None
        self.cursor = None
        self.ai_queue = queue.Queue()
        self.thinking = False
        self.think_started = 0.0
        self.eval_cp = 0
        self.flipped = BLACK in human_colors and WHITE not in human_colors
        self._maybe_start_ai()

    def start_game(self, human_colors):
        self._reset_button_focus()
        self._game_bg = None
        self.scene = "game"
        self._layout()
        self._ensure_fonts()
        self._new_game(human_colors)
        self._change_chess_thought(play_sound=False)

    def start_replay(self, entry, return_to=None):
        self._reset_button_focus()
        if return_to is None:
            if self.scene == "lesson":
                return_to = {"scene": "lesson"}
            else:
                return_to = {
                    "scene": "menu", "view": self.menu_view,
                    "category": self.library_filter, "page": self.library_page,
                    "course_id": self.active_course_id,
                    "focus_id": (entry.game.game_id if self.menu_view == "library"
                                 else "source_game" if self.menu_view == "course_about"
                                 else None),
                }
        self.replay_return = return_to
        self.scene = "replay"
        self.replay_entry = entry
        self.replay = ReplayController(entry.game)
        self.replay_autoplay = False
        self.replay_mainline = self._replay_move_labels()
        self.replay_scroll = 0
        self.replay_max_scroll = 0
        self.replay_visible_rows = 1
        self.replay_scroll_manual = False
        self.flipped = False
        self.thinking = False
        self._layout()
        self._ensure_fonts()
        self._game_bg = None
        self._sync_replay_position()
        self._change_chess_thought(play_sound=False)

    def start_lesson(self, entry, course_id=None):
        self._reset_button_focus()
        return_view = self.menu_view if self.scene == "menu" else self.lesson_return_view
        self.scene = "lesson"
        self.lesson_entry = entry
        self.lesson_course_id = course_id
        self.lesson_return_view = (
            "course" if self.lesson_course_id else
            return_view if return_view in ("opening_hub", "library")
            else "library")
        self.coach_profile = (self.game_library.player(
            entry.lesson.coach_player_id) if entry.lesson.coach_player_id
            and self.game_library else None)
        self.replay_autoplay = False
        self.thinking = False
        self.flipped = False
        self.lesson_scroll = 0
        self.lesson_message = ""
        record = None
        step_records = {}
        if self.progress_store is None and not self.progress_error:
            try:
                self.progress_store = ProgressStore()
            except ProgressStoreError as error:
                self.progress_error = str(error)
        if self.progress_store is not None:
            try:
                record = self.progress_store.load(entry.lesson.lesson_id)
                step_records = self.progress_store.load_step_progress(
                    entry.lesson.lesson_id, entry.lesson.content_revision)
            except Exception as error:
                self.progress_error = str(error)
        same_revision = bool(
            record and record.content_revision == entry.lesson.content_revision)
        totals = ({
            "attempts": record.attempts,
            "hints_used": record.hints_used,
            "reveals": record.reveals,
            "successes": record.successes,
        } if record else None)
        self.lesson = LessonController(
            entry.game, entry.lesson,
            resume_step=record.step_index if same_revision else 0,
            progress_totals=totals,
            completed=bool(same_revision and record.completed),
            step_progress=step_records,
            resume_assisted=bool(same_revision and record.active_assisted),
        )
        if self.lesson.state == READING and self.lesson.current_step.question:
            self.lesson.begin_question()
        if self.progress_error:
            self.lesson_message = "Progress is unavailable: " + self.progress_error
        self._layout()
        self._ensure_fonts()
        self._game_bg = None
        self._sync_lesson_position()
        self._save_lesson_progress()
        if self.coach_profile is None:
            self._change_chess_thought(play_sound=False)
        else:
            self._thought_previous = None
        if self.lesson_course_id:
            self._save_preferences(last_course_id=self.lesson_course_id)

    def _course_id_for_lesson(self, lesson_id):
        if self.game_library:
            for course in self.game_library.courses:
                if lesson_id in course.lesson_ids:
                    return course.course_id
        return None

    def _repeat_coach_advice(self):
        if self.coach_profile is None or self.lesson is None:
            return
        self.lesson_message = coach_advice(self.lesson, self.lesson_message)
        self._show_latest_lesson_message()
        sound.play("click")
        self._dirty = True

    def _sync_lesson_position(self, last_move=None):
        self.board = self.lesson.board
        self.moves = []
        self.sans = []
        self.last_move = (last_move if last_move is not None
                          else self.lesson.replay.current_move)
        self.selected = None
        self.legal_from_selected = []
        self.pending_promo = None
        self.cursor = None
        self.dragging = None
        self.drag_started = False
        self.status = game_status(self.board)
        self._dirty = True

    def _save_lesson_progress(self):
        if self.progress_store is None or self.lesson is None:
            return
        try:
            self.progress_store.save(self.lesson)
            self._course_summary_cache.clear()
        except Exception as error:
            self.progress_error = str(error)
            self.lesson_message = "Progress could not be saved: " + str(error)

    def _lesson_start_question(self):
        if self.lesson.state == READING:
            self.lesson.begin_question()
        self.lesson_message = ""
        self._sync_lesson_position()
        self._save_lesson_progress()

    def _show_latest_lesson_message(self):
        # The panel clamps this to its new content height on the next draw.
        self.lesson_scroll = 1_000_000

    def _lesson_hint(self):
        self.lesson_message = self.lesson.request_hint()
        self._show_latest_lesson_message()
        self._save_lesson_progress()
        self._dirty = True

    def _lesson_reveal(self):
        result = self.lesson.reveal()
        self.lesson_message = ""
        self._show_latest_lesson_message()
        self._sync_lesson_position(result.move)
        self._save_lesson_progress()

    def _lesson_retry(self):
        self.lesson.retry()
        self.lesson_message = ""
        self.lesson_scroll = 0
        self._sync_lesson_position()

    def _lesson_continue(self):
        self.lesson.continue_lesson()
        if self.lesson.state == READING and self.lesson.current_step.question:
            self.lesson.begin_question()
        self.lesson_scroll = 0
        self.lesson_message = ""
        self._sync_lesson_position()
        self._save_lesson_progress()

    def _lesson_begin_exploration(self):
        self.lesson.begin_exploration({"scroll": self.lesson_scroll})
        self.lesson_message = "Try any move you are curious about."
        self._sync_lesson_position()

    def _lesson_return(self):
        view_state = self.lesson.return_from_exploration()
        if isinstance(view_state, dict):
            self.lesson_scroll = int(view_state.get("scroll", 0))
        self.lesson_message = ""
        self._sync_lesson_position()

    def _lesson_restart(self):
        self.lesson.restart()
        if self.lesson.current_step.question:
            self.lesson.begin_question()
        self.lesson_scroll = 0
        self.lesson_message = ""
        self._sync_lesson_position()
        self._save_lesson_progress()

    def _next_path_entry(self):
        if self.lesson_course_id and self.game_library:
            course = self.game_library.course(self.lesson_course_id)
            if course:
                ids = course.lesson_ids
                lesson_id = self.lesson_entry.lesson.lesson_id
                if lesson_id in ids and ids.index(lesson_id) + 1 < len(ids):
                    return self.game_library.lesson_entry(
                        ids[ids.index(lesson_id) + 1])
            return None
        entries = self._path_entries()
        for index, entry in enumerate(entries[:-1]):
            if self.lesson_entry and entry.lesson.lesson_id == self.lesson_entry.lesson.lesson_id:
                return entries[index + 1]
        return None

    def _lesson_next(self):
        entry = self._next_path_entry()
        if entry is not None:
            self._save_lesson_progress()
            self.start_lesson(entry, course_id=self.lesson_course_id)

    def _apply_lesson_move(self, move):
        uci = str(move)
        if self.lesson.state == QUESTION:
            result = self.lesson.attempt_uci(
                uci, view_state={"scroll": self.lesson_scroll})
        elif self.lesson.state == EXPLORING:
            result = self.lesson.explore_uci(uci)
        else:
            return False
        self.lesson_message = ""
        if result.outcome != "illegal":
            self._show_latest_lesson_message()
        self._sync_lesson_position(result.move)
        self._save_lesson_progress()
        return result.outcome != "illegal"

    def _replay_move_labels(self):
        board = (self.replay.adapter.from_fen(self.replay.game.starting_fen)
                 if self.replay.game.starting_fen
                 else self.replay.adapter.initial_board())
        node = self.replay.game.root
        labels = []
        while node.children:
            node = node.children[0]
            number = board.fullmove_number
            side = board.side_to_move
            _, san = self.replay.adapter.apply_uci(board, node.uci)
            marker = "{}.".format(number) if side == WHITE else "{}...".format(number)
            labels.append((marker + " " + san, san))
        return tuple(labels)

    def _sync_replay_position(self):
        self.board = self.replay.board
        self.moves = []
        self.sans = list(self.replay.sans)
        self.last_move = self.replay.current_move
        self.selected = None
        self.legal_from_selected = []
        self.pending_promo = None
        self.cursor = None
        self.dragging = None
        self.drag_started = False
        self.status = game_status(self.board)
        self.replay_variations = self.replay.variations()
        self.replay_scroll_manual = False
        self._dirty = True

    def _scroll_replay(self, rows):
        if self.scene != "replay" or not rows:
            return
        self._stop_replay_autoplay()
        self.replay_scroll_manual = True
        self.replay_scroll = max(
            0, min(self.replay_max_scroll, self.replay_scroll + int(rows)))
        self._dirty = True

    def _stop_replay_autoplay(self):
        self.replay_autoplay = False

    def _replay_first(self):
        self._stop_replay_autoplay()
        self.replay.go_first()
        self._sync_replay_position()

    def _replay_previous(self):
        self._stop_replay_autoplay()
        if self.replay.previous():
            self._sync_replay_position()

    def _replay_next(self, variation_index=0, manual=True):
        if manual:
            self._stop_replay_autoplay()
        if self.replay.next(variation_index):
            self._sync_replay_position()
            return True
        return False

    def _replay_last(self):
        self._stop_replay_autoplay()
        self.replay.go_last()
        self._sync_replay_position()

    def _replay_jump_mainline(self, ply):
        self._stop_replay_autoplay()
        self.replay.jump_mainline(ply)
        self._sync_replay_position()

    def _toggle_replay_autoplay(self):
        if not self.replay.can_go_forward:
            self.replay.go_first()
            self._sync_replay_position()
        self.replay_autoplay = not self.replay_autoplay
        self.replay_next_at = time.monotonic() + self.replay_speeds[self.replay_speed_index]
        self._dirty = True

    def _cycle_replay_speed(self):
        self.replay_speed_index = (self.replay_speed_index + 1) % len(self.replay_speeds)
        self.replay_next_at = time.monotonic() + self.replay_speeds[self.replay_speed_index]
        self._save_preferences(replay_speed_index=self.replay_speed_index)
        self._dirty = True

    def _poll_replay_autoplay(self):
        if (self.scene != "replay" or not self.replay_autoplay
                or time.monotonic() < self.replay_next_at):
            return False
        if not self._replay_next(manual=False):
            self.replay_autoplay = False
            return True
        self.replay_next_at = time.monotonic() + self.replay_speeds[self.replay_speed_index]
        if self.replay.current_comment:
            self.replay_autoplay = False
        return True

    # ================================================================= AI
    def _ai_params(self):
        _, tl, dcap = DIFFICULTIES[self.difficulty]
        return tl, dcap

    def _maybe_start_ai(self):
        if self.status != "ongoing":
            return
        if self.board.side_to_move in self.human_colors:
            return
        if self.thinking:
            return
        self.thinking = True
        self.think_started = time.monotonic()
        tl, dcap = self._ai_params()
        snap = self.board.clone()
        result_queue = self.ai_queue

        def work():
            try:
                move, score, _pv, _n = ai.analyse(
                    snap, time_limit=tl, max_depth=dcap)
                result_queue.put((move, score, None))
            except Exception as error:
                result_queue.put((None, None, str(error)))

        threading.Thread(target=work, daemon=True).start()

    def _poll_ai(self):
        if not self.thinking:
            return False
        try:
            move, score, error = self.ai_queue.get_nowait()
        except queue.Empty:
            return False
        self.thinking = False
        if error is not None:
            self._flash("AI move failed: " + error)
            self._dirty = True
            return True
        self.eval_cp = score if self.board.side_to_move == WHITE else -score
        if move is not None:
            self._apply(move)
        return True

    # ================================================================= flow
    def _apply(self, move):
        victim = self.board.piece_at(move.to)
        san = notation.to_san(self.board, move)
        self.board.make_move(move)
        self.moves.append(move)
        self.sans.append(san)
        self.last_move = move
        self.selected = None
        self.legal_from_selected = []
        self.pending_promo = None
        self.status = game_status(self.board)

        if self.status != "ongoing":
            sound.play("end")
        elif in_check(self.board, self.board.side_to_move):
            sound.play("check")
        elif move.is_castle:
            sound.play("castle")
        elif victim or move.is_en_passant:
            sound.play("capture")
        else:
            sound.play("move")

        if self.board.side_to_move == WHITE and not self.thinking:
            self.eval_cp = ai.evaluate(self.board)
        self._dirty = True
        self._maybe_start_ai()

    def _takeback(self):
        if self.thinking or not self.moves:
            return
        drop = 1
        if self.human_colors and len(self.human_colors) == 1:
            drop = 2 if len(self.moves) >= 2 else 1
        drop = min(drop, len(self.moves))
        self.moves = self.moves[:-drop]
        self.sans = self.sans[:-drop]
        self.board = Board()
        for m in self.moves:
            self.board.make_move(m)
        self.last_move = self.moves[-1] if self.moves else None
        self.selected = None
        self.legal_from_selected = []
        self.pending_promo = None
        self.status = game_status(self.board)
        self.eval_cp = ai.evaluate(self.board)
        self._flash("Takeback")

    # ================================================================= input
    def _sq_to_px(self, sq):
        self._sync_board_view()
        return self.board_view.square_to_pixel(sq)

    def _px_to_sq(self, pos):
        self._sync_board_view()
        return self.board_view.pixel_to_square(pos)

    def _can_move_now(self):
        if self.scene == "lesson":
            return (self.lesson.state in (QUESTION, EXPLORING)
                    and self.status == "ongoing"
                    and self.pending_promo is None)
        return (self.scene == "game" and self.status == "ongoing"
                and not self.thinking and self.pending_promo is None
                and self.board.side_to_move in self.human_colors)

    def _select(self, sq):
        self.selected = sq
        self.legal_from_selected = [m for m in legal_moves(self.board) if m.frm == sq]
        if self.scene == "lesson" and self.legal_from_selected:
            if not self.move_hint_seen:
                self.move_hint_seen = True
                self._save_preferences(move_hint_seen=True)

    def _try_move_to(self, sq):
        cands = [m for m in self.legal_from_selected if m.to == sq]
        if not cands:
            return False
        if len(cands) > 1 and all(m.promo for m in cands):
            self.pending_promo = cands
            self._build_promo_buttons(sq)
        else:
            if self.scene == "lesson":
                self._apply_lesson_move(cands[0])
            else:
                self._apply(cands[0])
        return True

    def _on_mouse_down(self, pos):
        if self.pending_promo is not None:
            for index, b in enumerate(self._promo_buttons):
                if b.rect.collidepoint(pos):
                    self._button_focus = index
                    b.action()
                    return
            self._reset_button_focus()
            return
        if (self._portrait_hit_rect is not None
                and self._portrait_hit_rect.collidepoint(pos)):
            self._change_chess_thought()
            return
        if self.scene == "replay":
            for rect, ply in self._replay_move_hits:
                if rect.collidepoint(pos):
                    sound.play("click")
                    self._replay_jump_mainline(ply)
                    return
        buttons = self._menu_buttons if self.scene == "menu" else self._game_buttons
        for index, b in enumerate(buttons):
            if b.rect.collidepoint(pos):
                self._button_focus = index
                sound.play("click")
                b.action()
                return
        self._reset_button_focus()
        if not self._can_move_now():
            return
        sq = self._px_to_sq(pos)
        if sq is None:
            return
        piece = self.board.piece_at(sq)
        if self.selected is not None and self._try_move_to(sq):
            return
        if piece and piece[0] == self.board.side_to_move:
            self._select(sq)
            self.dragging = (sq, piece)
            self.drag_pos = pos
            self.drag_started = False
        else:
            self.selected = None
            self.legal_from_selected = []

    def _on_mouse_up(self, pos):
        if self.dragging is None:
            return
        from_sq, _ = self.dragging
        self.dragging = None
        sq = self._px_to_sq(pos)
        if sq is None or sq == from_sq:
            return
        self._try_move_to(sq)

    def _on_mouse_motion(self, pos):
        if self.dragging is not None:
            self.drag_pos = pos
            self.drag_started = True

    def _move_cursor(self, dr, dc):
        if self.flipped:
            dr, dc = -dr, -dc
        if self.cursor is None:
            self.cursor = (6, 4) if not self.flipped else (1, 4)
            return
        r, c = self.cursor
        self.cursor = (max(0, min(7, r + dr)), max(0, min(7, c + dc)))

    def _activate_cursor(self):
        if self.cursor is None or not self._can_move_now():
            return
        sq = self.cursor
        if self.selected is not None and self._try_move_to(sq):
            return
        piece = self.board.piece_at(sq)
        if piece and piece[0] == self.board.side_to_move:
            self._select(sq)
        else:
            self.selected = None
            self.legal_from_selected = []

    def _reset_button_focus(self):
        self._button_focus = None

    def _active_buttons(self):
        if self.pending_promo is not None:
            return self._promo_buttons
        return self._menu_buttons if self.scene == "menu" else self._game_buttons

    def _move_button_focus(self, reverse=False):
        buttons = self._active_buttons()
        if not buttons:
            self._button_focus = None
            return
        if self._button_focus is None:
            self._button_focus = len(buttons) - 1 if reverse else 0
        else:
            step = -1 if reverse else 1
            self._button_focus = (self._button_focus + step) % len(buttons)
        self._dirty = True

    def _activate_button_focus(self):
        buttons = self._active_buttons()
        if self._button_focus is None or self._button_focus >= len(buttons):
            return False
        sound.play("click")
        buttons[self._button_focus].action()
        return True

    # ================================================================= buttons
    def _open_colors(self):
        self._reset_button_focus()
        changed = self.menu_view != "colors"
        self.menu_view = "colors"
        self._menu_buttons = []
        if changed:
            self._change_chess_thought(play_sound=False)

    def _close_colors(self):
        self._reset_button_focus()
        self.menu_view = "main"
        self._menu_buttons = []
        self._change_chess_thought(play_sound=False)

    def _open_library(self, category="guided_game", page=0):
        self._reset_button_focus()
        changed = self.menu_view != "library" or self.library_filter != category
        if self.menu_view != "library":
            self.library_return = self.menu_view
        self.library_filter = category
        page_count = max(1, (len(self._library_entries()) + 4) // 5)
        page = page if type(page) is int else 0
        self.library_page = max(0, min(page, page_count - 1))
        self.menu_view = "library"
        if category != "replay":
            self._remember_learn_browse(view="library", category=category,
                                        page=self.library_page)
        self._menu_buttons = []
        if changed:
            self._change_chess_thought(play_sound=False)

    def _open_openings(self, page=0):
        self.library_return = "learn"
        self.course_page = self._clamp_course_page(page)
        self._remember_learn_browse(view="opening_hub", page=self.course_page)
        self._open_menu_section("opening_hub")

    def _clamp_course_page(self, page):
        count = (len(self.game_library.courses_for_category("opening"))
                 if self.game_library else 0)
        last = max(0, (count - 1) // 2)
        return max(0, min(page if type(page) is int else 0, last))

    def _change_course_page(self, delta):
        page = self._clamp_course_page(self.course_page + delta)
        if page != self.course_page:
            self.course_page = page
            self._remember_learn_browse(view="opening_hub", page=page)
            self._reset_button_focus()
            self._menu_buttons = []
            self._change_chess_thought(play_sound=False)
            self._dirty = True

    def _open_course(self, course_id):
        if self.game_library and self.game_library.course(course_id):
            self.active_course_id = course_id
            self._remember_learn_browse(
                view="course", course_id=course_id, page=self.course_page)
            self._save_preferences(last_course_id=course_id)
            self._open_menu_section("course")

    def _remember_learn_browse(self, **context):
        self.last_learn_browse = context
        self._save_preferences(last_learn_browse=context)

    def _has_learn_browse(self):
        context = self.last_learn_browse
        if not isinstance(context, dict):
            return False
        view = context.get("view")
        if view == "course":
            return bool(self.game_library and self.game_library.course(
                context.get("course_id")))
        return view == "opening_hub" or (view == "library" and
               context.get("category") in
               ("path", "guided_game", "opening", "endgame"))

    def _restore_learn_browse(self):
        if not self._has_learn_browse():
            return
        context = self.last_learn_browse
        if context["view"] == "course":
            self.course_page = self._clamp_course_page(context.get("page", 0))
            self._open_course(context["course_id"])
        elif context["view"] == "opening_hub":
            self._open_openings(context.get("page", 0))
        else:
            self._open_library(context["category"], context.get("page", 0))

    def _open_course_about(self):
        self._open_menu_section("course_about")

    def _watch_course_source(self):
        course = self.game_library.course(self.active_course_id)
        entry = next((item for item in self.game_library.entries
                      if item.game.game_id == course.source_game_id), None)
        if entry:
            self.start_replay(entry)

    def _watch_lesson_record(self):
        lesson = self.lesson_entry.lesson
        game_id = lesson.related_source_game_id or lesson.game_id
        entry = next((item for item in self.game_library.entries
                      if item.game.game_id == game_id), None)
        if entry is None:
            self._flash("This game is unavailable; return to the lesson.")
            return
        self.start_replay(entry, return_to={"scene": "lesson"})

    def _open_source_link(self, url):
        if url:
            try:
                webbrowser.open(url)
            except Exception as error:
                self._flash("Could not open source: {}".format(error))

    def _course_progress(self, course):
        done = self._course_summary(course).done_count
        return "{} of {} lessons done".format(done, len(course.lesson_ids))

    def _course_summary(self, course):
        key = (course.course_id, id(self.game_library), id(self.progress_store))
        if key not in self._course_summary_cache:
            try:
                summary = build_course_summary(
                    self.game_library, course, self.progress_store)
            except Exception as error:
                self.progress_error = str(error)
                summary = build_course_summary(self.game_library, course, None)
            self._course_summary_cache[key] = summary
        return self._course_summary_cache[key]

    def _course_missing_prerequisites(self, course):
        return self._course_summary(course).missing_prerequisites

    def _practise_course_basics(self):
        course = self.game_library.course(self.active_course_id)
        missing = self._course_missing_prerequisites(course)
        entry = self.game_library.lesson_entry(missing[0]) if missing else None
        if entry is None:
            self._flash("Opening basics is unavailable right now.")
            return
        self.start_lesson(entry, course_id=course.course_id)

    def _course_entry_status(self, entry):
        course = next((item for item in self.game_library.courses
                       if entry.lesson.lesson_id in item.lesson_ids), None)
        return (self._course_summary(course).status(entry.lesson.lesson_id)
                if course else "NEXT")

    def _continue_course(self):
        course = self.game_library.course(self.active_course_id)
        entries = self.game_library.course_lessons(course)
        entry = next((item for item in entries
                      if self._course_entry_status(item) in
                      ("NEXT", "IN PROGRESS")), entries[-1])
        self.start_lesson(entry, course_id=course.course_id)

    def _change_library_page(self, delta):
        entries = self._library_entries()
        page_count = max(1, (len(entries) + 4) // 5)
        page = max(0, min(page_count - 1, self.library_page + delta))
        if page != self.library_page:
            self.library_page = page
            if self.library_filter != "replay":
                self._remember_learn_browse(
                    view="library", category=self.library_filter, page=page)
            self._reset_button_focus()
            self._menu_buttons = []
            self._change_chess_thought(play_sound=False)
            self._dirty = True

    def _path_entries(self):
        entries = self.game_library.lesson_entries if self.game_library else ()
        by_id = {entry.lesson.lesson_id: entry for entry in entries
                 if entry.lesson}
        path = self.game_library.learning_path if self.game_library else ()
        return tuple(by_id[lesson_id] for lesson_id in path
                     if lesson_id in by_id)

    def _library_entries(self):
        if self.library_filter == "path":
            return self._path_entries()
        category = ("guided_game" if self.library_filter == "replay"
                    else self.library_filter)
        entries = ((self.game_library.entries if self.library_filter == "replay"
                    else self.game_library.lesson_entries)
                   if self.game_library else ())
        if self.library_filter == "replay":
            return tuple(entry for entry in entries if entry.category in
                         ("guided_game", "source_game"))
        return tuple(entry for entry in entries if entry.category == category)

    def _path_status(self, entry):
        if self.progress_store is None:
            return "NEXT" if entry == self._path_entries()[0] else "LATER"
        record = self.progress_store.load(
            entry.lesson.lesson_id, entry.lesson.content_revision)
        if record and record.completed:
            return "DONE" if record.attempts <= record.successes else "REVISIT"
        if record:
            return "IN PROGRESS"
        for previous in self._path_entries():
            if previous == entry:
                break
            earlier = self.progress_store.load(
                previous.lesson.lesson_id, previous.lesson.content_revision)
            if not earlier or not earlier.completed:
                return "LATER"
        return "NEXT"

    def _resume_entry(self):
        entries = self.game_library.lesson_entries if self.game_library else ()
        if self.progress_store is None:
            return None
        revisions = {item.lesson.lesson_id: item.lesson.content_revision
                     for item in entries if item.lesson}
        try:
            record = self.progress_store.latest_unfinished(revisions)
        except Exception as error:
            self.progress_error = str(error)
            return None
        return next((item for item in entries if item.lesson and record and
                     item.lesson.lesson_id == record.lesson_id), None)

    def _continue_learning(self):
        entries = self._path_entries()
        entry = self._resume_entry()
        if entry is None:
            entry = next((item for item in entries
                          if self._path_status(item) in ("NEXT", "IN PROGRESS")), None)
        if entry is None:
            entry = next((item for item in entries
                          if self._path_status(item) == "REVISIT"),
                         entries[-1] if entries else None)
        if entry is None:
            self._open_library()
            return
        self.start_lesson(
            entry, course_id=self._course_id_for_lesson(entry.lesson.lesson_id))

    def _close_library(self):
        self._reset_button_focus()
        self.menu_view = self.library_return
        self._menu_buttons = []
        self._change_chess_thought(play_sound=False)

    def _cycle_difficulty(self, d):
        self.difficulty = max(0, min(len(DIFFICULTIES) - 1, self.difficulty + d))
        self._save_preferences(difficulty=self.difficulty)

    def _set_style(self, name):
        self.board_style = name
        self._game_bg = self._preview = None
        self._save_preferences(board_style=name)

    def _set_white(self, col):
        self.white_col = col
        self._preview = None
        self._save_preferences(white_color=col)

    def _set_black(self, col):
        self.black_col = col
        self._preview = None
        self._save_preferences(black_color=col)

    def _set_text_scale(self, scale):
        valid = {value for _label, value in TEXT_SIZES}
        scale = float(scale)
        if scale not in valid or scale == self.text_scale:
            return
        self.text_scale = scale
        self._rebuild_ui_fonts()
        self._game_bg = None
        self._preview = None
        self._sync_board_view()
        if self.scene in ("replay", "lesson"):
            self._sync_study_view()
        self._save_preferences(text_scale=scale)
        self._dirty = True

    def _toggle_sound(self):
        self.sound_enabled = not self.sound_enabled
        sound.set_enabled(self.sound_enabled)
        self._save_preferences(sound_enabled=self.sound_enabled)
        self._dirty = True

    def _exit(self):
        self.running = False

    def _build_game_buttons(self):
        self._game_buttons = []
        specs = [
            ("New", lambda: self._new_game(self.human_colors)),
            ("Takeback", self._takeback),
            ("Flip", self._toggle_flip),
            ("Save PGN", self._save_pgn),
            ("Load PGN", self._load_pgn),
            ("Menu", self._to_menu),
        ]
        if not self.show_panel:
            return
        bw, bh, gap = (self.panel_w - 20) // 2, 30, 8
        x0 = self.panel_x + 8
        y0 = self.panel_y + self.panel_h - 14 - (bh + gap) * 3
        for i, (label, action) in enumerate(specs):
            col, row = i % 2, i // 2
            rect = (x0 + col * (bw + gap), y0 + row * (bh + gap), bw, bh)
            self._game_buttons.append(Button(rect, label, action))

    def _build_replay_buttons(self):
        self._game_buttons = []
        if not self.show_panel:
            return
        ix = self.panel_x + 14
        width = self.panel_w - 28
        child_sans = self.replay_variations
        if len(child_sans) > 1 and self.panel_h >= 500:
            y = self.panel_y + 342
            for index, san in enumerate(child_sans[:3]):
                label = ("Continue: " if index == 0 else "Alternative: ") + san
                self._game_buttons.append(Button(
                    (ix, y, width, 28), label,
                    lambda choice=index: self._replay_next(choice), kind="step"))
                y += 32

        button_y = self.panel_y + self.panel_h - 158
        gap = 7
        half = (width - gap) // 2
        speed = self.replay_speeds[self.replay_speed_index]
        specs = [
            ("|‹  First", self._replay_first),
            ("‹  Previous", self._replay_previous),
            ("Pause" if self.replay_autoplay else "Play", self._toggle_replay_autoplay),
            ("Next  ›", self._replay_next),
            ("Last  ›|", self._replay_last),
            ("Speed  {:.1f}s".format(speed), self._cycle_replay_speed),
            ("Flip", self._toggle_flip),
            ("Back", self._leave_replay),
        ]
        if self.panel_w < 280:
            specs = [
                ("First", self._replay_first),
                ("Prev", self._replay_previous),
                ("Pause" if self.replay_autoplay else "Play",
                 self._toggle_replay_autoplay),
                ("Next", self._replay_next),
                ("Last", self._replay_last),
                ("{:.1f}s".format(speed), self._cycle_replay_speed),
                ("Flip", self._toggle_flip),
                ("Back", self._leave_replay),
            ]
        for index, (label, action) in enumerate(specs):
            column, row = index % 2, index // 2
            self._game_buttons.append(Button(
                (ix + column * (half + gap), button_y + row * 36,
                 half, 29), label, action, kind="step"))

    def _build_lesson_buttons(self):
        self._game_buttons = []
        ix = self.panel_x + 14
        width = self.panel_w - 28
        gap = 7
        compact = self.win_w < 820
        columns = 2
        button_width = (width - gap * (columns - 1)) // columns
        state = self.lesson.state
        if state == READING:
            specs = [
                ("Start", self._lesson_start_question),
                ("Lessons", self._leave_lesson),
                ("Main menu", self._to_menu),
            ]
        elif state == QUESTION:
            specs = [
                ("Hint", self._lesson_hint),
                ("Show answer", self._lesson_reveal),
                ("Lessons", self._leave_lesson),
                ("Main menu", self._to_menu),
            ]
        elif state == FEEDBACK:
            if self.lesson.step_solved:
                primary = ("Finish lesson" if self.lesson.step_index + 1
                           == len(self.lesson.resolved_steps) else "Next step")
                specs = [(primary, self._lesson_continue),
                         ("Try other move", self._lesson_begin_exploration)]
            else:
                specs = [("Try again", self._lesson_retry),
                         ("Show answer", self._lesson_reveal)]
            specs += [
                ("Lessons", self._leave_lesson),
                ("Main menu", self._to_menu),
            ]
        elif state == EXPLORING:
            specs = [
                ("Back to lesson", self._lesson_return),
                ("Lessons", self._leave_lesson),
                ("Main menu", self._to_menu),
            ]
        else:
            source_id = self.lesson_entry.lesson.related_source_game_id
            specs = [
                ("Try again", self._lesson_restart),
                ("Watch archival game" if source_id else "Replay practice",
                 self._watch_lesson_record),
                ("Lessons", self._leave_lesson),
                ("Main menu", self._to_menu),
            ]
            if self._next_path_entry() is not None:
                specs.insert(0, ("Next lesson", self._lesson_next))
        if compact or self.text_scale >= 1.4:
            short = {"Main menu": "Menu", "Show answer": "Answer",
                     "Try other move": "Other move",
                     "Back to lesson": "Back to lesson",
                     "Watch archival game": "Watch game",
                     "Replay practice": "Replay",
                     "Finish lesson": "Finish"}
            short["Next lesson"] = "Next"
            short["Next step"] = "Next step"
            specs = [(short.get(label, label), action)
                     for label, action in specs]
        rows = (len(specs) + columns - 1) // columns
        button_y = self.panel_y + self.panel_h - 12 - rows * 36
        for index, (label, action) in enumerate(specs):
            column, row = index % columns, index // columns
            self._game_buttons.append(Button(
                (ix + column * (button_width + gap), button_y + row * 36,
                 button_width, 29), label, action,
                kind="cta" if index == 0 and state != QUESTION else "step"))

    def _build_promo_buttons(self, sq):
        self._promo_buttons = []
        px, py = self._sq_to_px(sq)
        color = self.board.side_to_move
        top = min(py, self.board_y + self.board_px - 4 * self.SQ)
        for i, t in enumerate(["q", "r", "b", "n"]):
            rect = (px, top + i * self.SQ, self.SQ, self.SQ)
            self._promo_buttons.append(
                Button(rect, color + t, lambda t=t: self._choose_promo(t)))

    def _choose_promo(self, t):
        for m in self.pending_promo:
            if m.promo == t:
                if self.scene == "lesson":
                    self._apply_lesson_move(m)
                else:
                    self._apply(m)
                return

    def _toggle_flip(self):
        self.flipped = not self.flipped
        self._game_bg = None

    def _to_menu(self):
        self._reset_button_focus()
        self.replay_autoplay = False
        if self.scene == "lesson":
            self._save_lesson_progress()
        self.scene = "menu"
        self.menu_view = "main"
        self.coach_profile = None
        self._menu_buttons = []
        self._maybe_reload_theme()
        self._change_chess_thought(play_sound=False)

    def _leave_replay(self):
        self._reset_button_focus()
        self.replay_autoplay = False
        route = self.replay_return or {"scene": "menu", "view": "library"}
        if route["scene"] == "lesson":
            self.scene = "lesson"
            self._layout()
            self._ensure_fonts()
            self._game_bg = None
            self._sync_lesson_position()
            self._build_lesson_buttons()
            return
        self.scene = "menu"
        self.menu_view = route["view"]
        self.library_filter = route.get("category", self.library_filter)
        self.library_page = route.get("page", self.library_page)
        self.active_course_id = route.get("course_id", self.active_course_id)
        self._menu_buttons = []
        self._maybe_reload_theme()
        self._change_chess_thought(play_sound=False)
        self._build_menu_buttons()
        focus_id = route.get("focus_id")
        for index, button in enumerate(self._menu_buttons):
            if focus_id is not None and button.value == focus_id:
                self._button_focus = index
                break

    def _leave_lesson(self):
        self._reset_button_focus()
        self._save_lesson_progress()
        self.scene = "menu"
        self.menu_view = self.lesson_return_view
        if self.lesson_course_id:
            self.active_course_id = self.lesson_course_id
        self.coach_profile = None
        self._menu_buttons = []
        self._maybe_reload_theme()
        self._change_chess_thought(play_sound=False)

    # ================================================================= files
    def _flash(self, msg):
        self.toast = msg
        self.toast_until = time.monotonic() + 2.5

    def _save_pgn(self):
        result = {"checkmate": "1-0" if self.board.side_to_move == BLACK else "0-1",
                  "stalemate": "1/2-1/2"}.get(self.status, "*")
        if self.status.startswith("draw"):
            result = "1/2-1/2"
        try:
            with open(_PGN_PATH, "w") as f:
                f.write(notation.game_to_pgn(self.moves, result=result))
            self._flash(f"Saved -> {os.path.basename(_PGN_PATH)}")
        except OSError as e:
            self._flash(f"Save failed: {e}")

    def _load_pgn(self):
        if self.thinking:
            return
        try:
            with open(_PGN_PATH) as f:
                mvs = notation.pgn_to_moves(f.read())
        except (OSError, ValueError) as e:
            self._flash(f"Load failed: {e}")
            return
        self.board = Board()
        self.moves, self.sans = [], []
        for m in mvs:
            self.sans.append(notation.to_san(self.board, m))
            self.board.make_move(m)
            self.moves.append(m)
        self.last_move = self.moves[-1] if self.moves else None
        self.selected = None
        self.legal_from_selected = []
        self.pending_promo = None
        self.status = game_status(self.board)
        self.eval_cp = ai.evaluate(self.board)
        self._flash(f"Loaded {len(mvs)} moves")
        self._maybe_start_ai()

    # ================================================================= render
    def _ensure_menu_bg(self):
        key = (self.win_w, self.win_h, self.pal.name, self.pal.mode)
        if self._menu_bg is not None and self._menu_bg_key == key:
            return
        surf = _vgradient(self.win_w, self.win_h,
                          self.pal.menu_bg_top, self.pal.menu_bg_bot)
        _edge_vignette(surf, self.pal.mode, reach=110)
        self._menu_bg = surf
        self._menu_bg_key = key

    def _ensure_game_bg(self):
        key = (self.scene, self.board_style, self.flipped,
               self.board_x, self.board_y, self.board_px, self.win_w, self.win_h,
               self.pal.name, self.pal.mode)
        if self._game_bg is not None and self._game_bg_key == key:
            return
        surf = _vgradient(self.win_w, self.win_h, self.pal.bg, self.pal.bg_dim)
        _paint_board(surf, self.board_x, self.board_y, self.board_px,
                     self._style_def(self.board_style), random.Random(0xB0A4D5),
                     coord_font=self.coord_font, flipped=self.flipped,
                     frame=self.frame, radius=max(4, self.pal.rounding))
        _edge_vignette(surf, self.pal.mode)
        self._game_bg = surf
        self._game_bg_key = key

    def _draw(self):
        self._portrait_hit_rect = None
        thought_progress = self._thought_progress()
        lesson_thought = (coach_thought(
            self.coach_profile, self.lesson, self.lesson_message)
            if self.scene == "lesson" and self.coach_profile else self.chess_thought)
        if self.scene == "menu":
            self._draw_menu(thought_progress)
        else:
            self._ensure_game_bg()
            self.screen.blit(self._game_bg, (0, 0))
            self._draw_board()
            if self._board_thought_rect:
                self._portrait_hit_rect = self._board_thought_rect.copy()
                draw_chess_thought(
                    self.screen, self._board_thought_rect,
                    lesson_thought, self.status_font, self.text_font,
                    self.tag_font, self.pal, compact=True,
                    previous=(None if self.coach_profile else self._thought_previous),
                    progress=thought_progress)
            if self.show_panel:
                if self.scene == "replay":
                    self._draw_replay_panel(thought_progress)
                elif self.scene == "lesson":
                    self._draw_lesson_panel(thought_progress)
                else:
                    self._draw_panel(thought_progress)
            self._draw_status()
            if self.scene in ("game", "lesson") and self.pending_promo is not None:
                self._draw_promo()
        pygame.display.flip()

    # ---- menu -------------------------------------------------------------
    def _draw_menu(self, thought_progress=1.0):
        if not self._menu_buttons:
            self._build_menu_buttons()
        self._ensure_menu_bg()
        self.screen.blit(self._menu_bg, (0, 0))
        p = self.pal
        cx = self.win_w // 2
        colors_view = self.menu_view == "colors"
        library_view = self.menu_view == "library"
        rad = min(p.rounding, 14) if p.rounding else 0

        if not library_view and not colors_view and self._feature_rect.top >= 30:
            brand = self.status_font.render("Uroschess", True, p.text)
            self.screen.blit(brand, brand.get_rect(center=(cx, 17)))

        mx, my = pygame.mouse.get_pos()
        card = self._menu_card
        _round_rect_alpha(self.screen, card, (*p.panel, 235), rad)
        _hairline(self.screen, card, p.panel_line, rad)

        if colors_view:
            self._draw_board_preview(self._preview_rect)

        for text, hx, hy in self._menu_heads:
            heading = _fit_text(self.small_font, text,
                                max(30, card.right - hx - 12))
            self.screen.blit(self.small_font.render(heading, True, p.accent),
                             (hx, hy))
        for index, b in enumerate(self._menu_buttons):
            self._draw_menu_button(
                b, b.rect.collidepoint(mx, my), rad,
                focused=index == self._button_focus)

        if self.menu_view == "course_about" and self.game_library:
            course = self.game_library.course(self.active_course_id)
            if course:
                draw_course_about(
                    self.screen, card, course,
                    self.game_library.player(course.player_id),
                    self.game_library.games_by_id[course.source_game_id],
                    self.small_font, self.tag_font, p)

        if self.menu_view == "course" and self.game_library:
            course = self.game_library.course(self.active_course_id)
            if course:
                draw_player_card(
                    self.screen, self._course_profile_rect,
                    self.game_library.player(course.player_id), course,
                    p, self.status_font, self.small_font, self.tag_font,
                    progress=self._course_progress(course))

        self._portrait_hit_rect = None
        if self._feature_rect.h >= 60:
            course = (self.game_library.course(self.active_course_id)
                      if self.menu_view in ("course", "course_about")
                      and self.game_library else None)
            player = (self.game_library.player(course.player_id)
                      if course else None)
            course_advice = player.intro if player else ""
            if course:
                statuses = [self._course_entry_status(entry) for entry in
                            self.game_library.course_lessons(course)]
                if all(status in ("DONE", "REVISIT") for status in statuses):
                    course_advice = (
                        "Course finished. Revisit your try-alone lesson."
                        if "REVISIT" in statuses else
                        "Course complete! Try this idea in your own games.")
            thought = (ChessThought(player.name, player.short_name,
                                   course_advice, player.portrait, "")
                       if player else self.chess_thought)
            if player is None:
                self._portrait_hit_rect = self._feature_rect.copy()
            draw_chess_thought(
                self.screen, self._feature_rect, thought,
                self.status_font, self.text_font, self.tag_font, self.pal,
                compact=True,
                previous=None if player else self._thought_previous,
                progress=thought_progress)

        if library_view:
            available = bool(self._library_entries())
            if not available:
                empty = self.text_font.render(
                    "No valid lessons are available here.", True, p.text)
                self.screen.blit(empty, empty.get_rect(center=card.center))
            if self.library_errors:
                message = "Some content could not be loaded: " + self.library_errors[0]
                lines = _wrap_text(self.small_font, message, card.w - 56)[:3]
                y = card.bottom - 64
                for line in lines:
                    self.screen.blit(self.small_font.render(line, True, p.bad),
                                     (card.x + 28, y))
                    y += 16

        if colors_view:
            hint = "choose board, pieces, text, and sound   ·   Esc  back"
        elif library_view:
            hint = ("choose a game   ·   Esc  back"
                    if self.library_filter == "replay"
                    else "choose a lesson   ·   Esc  back")
        else:
            hint = "choose Learn or Play   ·   keyboard and mouse supported"
        if self.win_h >= 730:
            hs = self.small_font.render(hint, True, p.text_dim)
            self.screen.blit(hs, hs.get_rect(center=(cx, self.win_h - 22)))
        if colors_view and self.preferences_error:
            warning = self.small_font.render(
                "Preferences could not be loaded or saved.", True, p.bad)
            self.screen.blit(warning, (card.centerx + 26, card.bottom - 22))

    def _draw_menu_button(self, b, hot, rad, focused=False):
        p = self.pal
        if b.kind == "player":
            course = self.game_library.course(b.value)
            player = self.game_library.player(course.player_id)
            draw_player_card(
                self.screen, b.rect, player, course, p,
                self.status_font, self.small_font, self.tag_font,
                hot=hot, focused=focused,
                progress=self._course_progress(course))
            return
        if b.kind in ("swatchW", "swatchB"):
            sel = (b.color == self.white_col if b.kind == "swatchW"
                   else b.color == self.black_col)
            if sel:
                pygame.draw.rect(self.screen, p.accent,
                                 pygame.Rect(b.rect).inflate(8, 8),
                                 border_radius=rad + 3)
            pygame.draw.rect(self.screen, b.color, b.rect, border_radius=rad)
            pygame.draw.rect(self.screen, p.text if (sel or hot) else p.panel_line,
                             b.rect, width=2, border_radius=rad)
            if focused:
                draw_focus_ring(self.screen, b.rect, p.accent, rad)
            return
        if b.kind == "exit":
            fill = _mix(p.panel, p.bad, 0.30 if not hot else 0.5)
            tcol = _text_for(fill)
        elif b.kind == "cta":
            fill = p.accent if not hot else _lighten(p.accent, 12)
            tcol = p.on_accent
        elif b.kind in ("style", "textsize", "toggle"):
            active = (b.label == self.board_style if b.kind == "style"
                      else (b.value == self.text_scale if b.kind == "textsize"
                            else self.sound_enabled))
            fill = p.accent if active else (p.btn_hot if hot else p.btn)
            tcol = p.on_accent if active else p.text
        elif b.kind == "library":
            fill = p.btn_hot if hot else p.btn
            _flat_button(self.screen, b.rect, fill, p.panel_line, rad)
            inset = b.rect.inflate(-28, -8)
            title = _fit_text(self.text_font, b.label, inset.w)
            self.screen.blit(self.text_font.render(title, True, p.text),
                             (inset.x, b.rect.y + 7))
            detail_y = b.rect.y + max(32, self.text_font.get_linesize() + 9)
            line_height = self.small_font.get_linesize()
            max_lines = max(1, (b.rect.bottom - 4 - detail_y) // line_height)
            lines = _wrap_text(self.small_font, b.detail, inset.w)
            for index, line in enumerate(lines[:max_lines]):
                if index == max_lines - 1 and len(lines) > max_lines:
                    line += "…"
                line = _fit_text(self.small_font, line, inset.w)
                self.screen.blit(self.small_font.render(line, True, p.text),
                                 (inset.x, detail_y + index * line_height))
            if focused:
                draw_focus_ring(self.screen, b.rect, p.accent, rad)
            return
        else:
            fill = p.btn_hot if hot else p.btn
            tcol = p.text
        _flat_button(self.screen, b.rect, fill, p.panel_line, rad)
        font = self.text_font if b.kind in ("normal", "exit", "cta") else self.small_font
        s = font.render(b.label, True, tcol)
        self.screen.blit(s, s.get_rect(center=b.rect.center))
        if focused:
            draw_focus_ring(self.screen, b.rect, p.accent, rad)

    def _draw_board_preview(self, rect):
        p = self.pal
        key = (self.board_style, tuple(self.white_col), tuple(self.black_col),
               rect.w, rect.h, p.name)
        if self._preview is None or self._preview_key != key:
            surf = pygame.Surface(rect.size, pygame.SRCALPHA)
            bp = (min(rect.w, rect.h) - 20) // 8 * 8
            ox, oy = (rect.w - bp) // 2, (rect.h - bp) // 2
            _paint_board(surf, ox, oy, bp, self._style_def(self.board_style),
                         random.Random(0x5EED), frame=9, radius=6)
            sq = bp // 8
            demo = {(7, 4): "wk", (7, 3): "wq", (6, 4): "wp", (5, 2): "wn",
                    (0, 4): "bk", (0, 3): "bq", (1, 4): "bp", (2, 5): "bb"}
            for (r, c), pc in demo.items():
                fill = self.white_col if pc[0] == WHITE else self.black_col
                self._blit_glyph(surf, pc[1], fill, ox + c * sq + sq // 2,
                                 oy + r * sq + sq // 2, sq)
            self._preview = surf
            self._preview_key = key
        self.screen.blit(self._preview, rect.topleft)

    def _blit_glyph(self, surf, ptype, fill, cx, cy, box):
        if self.use_glyphs:
            k = box / max(1, self._piece_size)
            g = GLYPHS[ptype]

            def scaled(color):
                s = self.piece_font.render(g, True, color)
                return pygame.transform.smoothscale(
                    s, (max(1, int(s.get_width() * k)),
                        max(1, int(s.get_height() * k))))

            outline = scaled(_outline_for(fill))
            for ox, oy in ((-2, 0), (2, 0), (0, -2), (0, 2)):
                surf.blit(outline, outline.get_rect(center=(cx + ox * k, cy + oy * k)))
            body = scaled(fill)
            surf.blit(body, body.get_rect(center=(cx, cy)))
        else:
            rad = int(box * 0.36)
            pygame.draw.circle(surf, fill, (cx, cy), rad)
            pygame.draw.circle(surf, _outline_for(fill), (cx, cy), rad, 2)
            s = self.small_font.render(LETTERS[ptype], True, _text_for(fill))
            surf.blit(s, s.get_rect(center=(cx, cy)))

    # ---- board ----------------------------------------------------------
    def _draw_board(self):
        p = self.pal
        checked = []
        if self.status in ("ongoing", "checkmate"):
            for color in (WHITE, BLACK):
                if in_check(self.board, color):
                    checked.append(self.board.king_square(color))

        legal_destinations = [
            (move.to, bool(self.board.piece_at(move.to)) or move.is_en_passant)
            for move in self.legal_from_selected
        ]
        dragging = None
        if self.dragging:
            dragging = self.dragging[0], self.dragging[1], self.drag_started
        self._sync_board_view()
        lesson_highlights = ()
        lesson_arrows = ()
        if self.scene == "lesson":
            lesson_highlights = self.lesson.visible_highlights
            lesson_arrows = self.lesson.visible_arrows
            if (self.lesson.state == QUESTION and self.selected is None
                    and self.lesson.lesson.initial_help
                    and self.lesson.current_step.practice_mode == "guided"):
                sources = {move.frm for move in legal_moves(self.board)}
                gentle = tuple(SquareHighlight(
                    chr(ord("a") + col) + str(8 - row), "focus")
                    for row, col in sorted(sources))
                lesson_highlights = tuple(lesson_highlights) + gentle
        self.board_view.draw_position(
            self.board,
            white_color=self.white_col,
            black_color=self.black_col,
            last_move=self.last_move,
            selected=self.selected,
            legal_destinations=legal_destinations,
            cursor=self.cursor,
            checked_squares=checked,
            dragging=dragging,
            drag_position=self.drag_pos,
            lesson_highlights=lesson_highlights,
            lesson_arrows=lesson_arrows,
            selection_color=p.sel,
            last_move_color=p.lastmove,
            check_color=p.check,
            legal_color=p.dot,
            cursor_color=p.accent,
        )

    def _draw_piece(self, piece, cx, cy):
        self._sync_board_view()
        self.board_view.draw_piece(
            piece, (cx, cy), self.white_col, self.black_col)

    # ---- panel --------------------------------------------------------
    def _draw_panel(self, thought_progress=1.0):
        p = self.pal
        rad = p.rounding
        card = pygame.Rect(self.panel_x, self.panel_y, self.panel_w, self.panel_h)
        _round_rect_alpha(self.screen, card, (*p.panel, 255), rad)
        _hairline(self.screen, card, p.panel_line, rad)

        ix = self.panel_x + 14
        iw = self.panel_w - 28

        by, bh = self.panel_y + 16, 14
        if self._portrait_in_panel:
            portrait = pygame.Rect(ix, by, iw, 260)
            self._portrait_hit_rect = portrait
            draw_chess_thought(
                self.screen, portrait, self.chess_thought,
                self.status_font, self.small_font, self.tag_font, p,
                previous=self._thought_previous,
                progress=thought_progress)
            by = portrait.bottom + 16
        cp = max(-1000, min(1000, self.eval_cp))
        frac = 0.5 + cp / 2000.0
        _round_rect_alpha(self.screen, (ix, by, iw, bh), (*p.field, 255), 4)
        _round_rect_alpha(self.screen, (ix, by, max(3, int(iw * frac)), bh),
                          (*p.accent, 255), 4)
        tag = f"{cp / 100:+.2f}" if abs(self.eval_cp) < ai.MATE_THRESHOLD else "M"
        self.screen.blit(self.tag_font.render(tag, True, p.text_dim),
                         (ix, by + bh + 4))

        cap_w, cap_b, adv = self._captured()
        self._draw_captured(cap_w, ix, by + bh + 20)
        self._draw_captured(cap_b, ix, by + bh + 42)
        if adv:
            side = "White" if adv > 0 else "Black"
            s = self.tag_font.render(f"{side} +{abs(adv)}", True, p.text_dim)
            self.screen.blit(s, (ix + iw - s.get_width(), by + bh + 20))

        top = by + bh + 66
        bottom = (self.panel_y + self.panel_h - 14 - (30 + 8) * 3 - 10
                  if self.show_panel else self.panel_y + self.panel_h - 14)
        _round_rect_alpha(self.screen, (ix, top, iw, bottom - top),
                          (*p.field, 255), max(4, min(rad, 8)))
        line_h = 17
        rows = (len(self.sans) + 1) // 2
        visible = max(1, (bottom - top - 10) // line_h)
        start = max(0, rows - visible)
        y = top + 6
        for i in range(start, rows):
            wsan = self.sans[2 * i] if 2 * i < len(self.sans) else ""
            bsan = self.sans[2 * i + 1] if 2 * i + 1 < len(self.sans) else ""
            num = self.mono_font.render(f"{i + 1:>2}.", True, p.text_dim)
            self.screen.blit(num, (ix + 8, y))
            cur = len(self.sans) - 1
            for j, san in ((2 * i, wsan), (2 * i + 1, bsan)):
                if not san:
                    continue
                is_cur = j == cur
                col = p.on_accent if is_cur else p.text
                s = self.mono_font.render(san, True, col)
                xx = ix + 42 + (0 if j % 2 == 0 else 84)
                if is_cur:
                    _round_rect_alpha(self.screen,
                                      (xx - 4, y - 1, s.get_width() + 8, line_h),
                                      (*p.accent, 255), 4)
                self.screen.blit(s, (xx, y))
            y += line_h

        mx, my = pygame.mouse.get_pos()
        for index, btn in enumerate(self._game_buttons):
            hot = btn.rect.collidepoint(mx, my)
            _flat_button(self.screen, btn.rect,
                         p.btn_hot if hot else p.btn, p.panel_line,
                         max(4, min(rad, 8)))
            s = self.small_font.render(btn.label, True, p.text)
            self.screen.blit(s, s.get_rect(center=btn.rect.center))
            if index == self._button_focus:
                draw_focus_ring(
                    self.screen, btn.rect, p.accent,
                    max(4, min(rad, 8)))

    def _draw_replay_panel(self, thought_progress=1.0):
        self._sync_study_view()
        panel = pygame.Rect(
            self.panel_x, self.panel_y, self.panel_w, self.panel_h)
        (self._replay_move_hits, self.replay_scroll,
         self.replay_max_scroll,
         self.replay_visible_rows) = self.study_view.draw_replay_panel(
            panel, self.replay, self.replay_entry, self.replay_mainline,
            self.replay_variations, self._game_buttons, pygame.mouse.get_pos(),
            self._button_focus,
            self.replay_scroll if self.replay_scroll_manual else None,
            self.chess_thought if self._portrait_in_panel else None,
            self._thought_previous if self._portrait_in_panel else None,
            thought_progress)
        if self.study_view.thought_hit_rect is not None:
            self._portrait_hit_rect = self.study_view.thought_hit_rect

    def _draw_lesson_panel(self, thought_progress=1.0):
        self._sync_study_view()
        panel = pygame.Rect(
            self.panel_x, self.panel_y, self.panel_w, self.panel_h)
        self.lesson_max_scroll = self.study_view.draw_lesson_panel(
            panel, self.lesson, self._game_buttons,
            pygame.mouse.get_pos(), self.lesson_scroll, self.lesson_message,
            self._button_focus,
            (coach_thought(self.coach_profile, self.lesson, self.lesson_message)
             if self.coach_profile else self.chess_thought)
            if self._portrait_in_panel else None,
            None if self.coach_profile else self._thought_previous,
            thought_progress,
            show_move_hint=(not self.move_hint_seen and
                            self.lesson.lesson.initial_help and
                            self.lesson.current_step.practice_mode == "guided"),
            coach_label=(self.coach_profile.short_name
                         if self.coach_profile else ""))
        if self._portrait_in_panel:
            self._portrait_hit_rect = self.study_view.thought_hit_rect
        self.lesson_scroll = max(
            0, min(self.lesson_scroll, self.lesson_max_scroll))

    def _captured(self):
        counts = {WHITE: {}, BLACK: {}}
        for row in self.board.grid:
            for pc in row:
                if pc:
                    counts[pc[0]][pc[1]] = counts[pc[0]].get(pc[1], 0) + 1
        start = {"p": 8, "n": 2, "b": 2, "r": 2, "q": 1}
        cap_by_white, cap_by_black = [], []
        val_w = val_b = 0
        for t, n in start.items():
            miss_b = n - counts[BLACK].get(t, 0)
            miss_w = n - counts[WHITE].get(t, 0)
            cap_by_white += [BLACK + t] * max(0, miss_b)
            cap_by_black += [WHITE + t] * max(0, miss_w)
            val_w += max(0, miss_b) * VALUES[t]
            val_b += max(0, miss_w) * VALUES[t]
        return cap_by_white, cap_by_black, (val_w - val_b) // 100

    def _draw_captured(self, pieces, x, y):
        order = "qrbnp"
        for i, pc in enumerate(sorted(pieces, key=lambda p: order.index(p[1]))):
            self._blit_glyph(self.screen, pc[1],
                             self.white_col if pc[0] == WHITE else self.black_col,
                             x + i * 13 + 6, y + 8, 18)

    def _draw_status(self):
        p = self.pal
        rad = min(p.rounding, 12) if p.rounding else 0
        rect = pygame.Rect(self.status_x, self.status_y, self.status_w,
                           self.status_h)
        _round_rect_alpha(self.screen, rect, (*p.panel, 255), rad)
        _hairline(self.screen, rect, p.panel_line, rad)

        now = time.monotonic()
        hot = False
        if self.toast and now < self.toast_until:
            text, hot = self.toast, True
        elif self.scene == "replay":
            total = len(self.replay_mainline)
            on_mainline = all(index == 0 for index in self.replay.path)
            if self.win_w < 820:
                text = "Replay {}/{}  ·  use controls below".format(
                    self.replay.ply, total)
            elif not self.replay.can_go_forward and on_mainline and self.replay.ply == total:
                result_text = {
                    "1-0": "White won", "0-1": "Black won",
                    "1/2-1/2": "Draw", "*": "Game ended",
                }[self.replay.game.result]
                text = "End of game — {}   ·   ← previous   Home start".format(
                    result_text)
            elif not self.replay.can_go_forward:
                text = "End of variation   ·   ← previous   Home start"
            else:
                mode = "variation" if any(i != 0 for i in self.replay.path) else "main line"
                text = "Replay {}/{} — {}   ·   ←/→ navigate   Space autoplay".format(
                    self.replay.ply, total, mode)
        elif self.scene == "lesson":
            if self.lesson.state == COMPLETED:
                text = "Lesson finished"
            elif self.lesson.state == EXPLORING:
                text = "Try a different move"
            elif self.lesson.state == QUESTION:
                mover = "White" if self.board.side_to_move == WHITE else "Black"
                text = "{} to move".format(mover)
            elif self.lesson.state == FEEDBACK:
                text = "Move reviewed"
            else:
                text = "Read the question"
        elif self.status == "checkmate":
            winner = "White" if self.board.side_to_move == BLACK else "Black"
            text = f"Checkmate — {winner} wins   ·   R new game"
        elif self.status == "stalemate":
            text = "Stalemate — draw   ·   R new game"
        elif self.status == "draw-fifty":
            text = "Draw — 50-move rule   ·   R new game"
        elif self.status == "draw-repetition":
            text = "Draw — threefold repetition   ·   R new game"
        elif self.status == "draw-material":
            text = "Draw — insufficient material   ·   R new game"
        elif self.thinking:
            text = "AI is thinking" + "." * (1 + int((now - self.think_started) * 2) % 3)
        else:
            mover = "White" if self.board.side_to_move == WHITE else "Black"
            who = "Your move" if self.board.side_to_move in self.human_colors else "AI"
            text = f"{who} — {mover} to move"
        text = _fit_text(self.status_font, text, rect.w - 28)
        s = self.status_font.render(text, True, p.accent if hot else p.text)
        self.screen.blit(s, s.get_rect(midleft=(rect.x + 14, rect.centery)))

    def _draw_promo(self):
        p = self.pal
        shade = pygame.Surface((self.board_px, self.board_px), pygame.SRCALPHA)
        shade.fill((0, 0, 0, 130))
        self.screen.blit(shade, (self.board_x, self.board_y))
        mx, my = pygame.mouse.get_pos()
        for index, b in enumerate(self._promo_buttons):
            hot = b.rect.collidepoint(mx, my)
            _round_rect_alpha(self.screen, b.rect,
                              (*(p.btn_hot if hot else p.panel), 255), 6)
            pygame.draw.rect(self.screen, p.accent, b.rect, 2, border_radius=6)
            self._draw_piece(b.label, b.rect.centerx, b.rect.centery)
            if index == self._button_focus:
                draw_focus_ring(self.screen, b.rect, p.accent, 6)

    # ================================================================= loop
    def run(self):
        _redraw_events = (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN,
                          pygame.MOUSEBUTTONUP)
        while self.running:
            resize_to = None
            need_draw = self._dirty
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.VIDEORESIZE:
                    resize_to = (event.w, event.h)  # coalesce: apply last only
                elif event.type == pygame.KEYDOWN:
                    if not self._on_key(event.key, event.mod):
                        self.running = False
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    self._on_mouse_down(event.pos)
                elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                    self._on_mouse_up(event.pos)
                elif event.type == pygame.MOUSEMOTION:
                    self._on_mouse_motion(event.pos)
                    if self.dragging is not None or self._hover_changed(event.pos):
                        need_draw = True
                elif event.type == pygame.MOUSEWHEEL:
                    if self.scene == "menu" and self.menu_view == "library":
                        self._change_library_page(-event.y)
                        need_draw = True
                    elif self.scene == "menu" and self.menu_view == "opening_hub":
                        self._change_course_page(-event.y)
                        need_draw = True
                    elif self.scene == "lesson":
                        self.lesson_scroll = max(
                            0, min(self.lesson_max_scroll,
                                   self.lesson_scroll - event.y * 32))
                        need_draw = True
                    elif self.scene == "replay":
                        self._scroll_replay(-event.y * 3)
                        need_draw = True
                if event.type in _redraw_events:
                    need_draw = True

            if resize_to is not None and self._on_resize(*resize_to):
                need_draw = True
            if self.toast and time.monotonic() >= self.toast_until:
                self.toast = ""
                need_draw = True

            if self.scene == "menu":
                self._build_menu_buttons()
            elif self.scene == "replay":
                self._build_replay_buttons()
            elif self.scene == "lesson":
                self._build_lesson_buttons()
            else:
                self._build_game_buttons()
            if self.scene == "game" and self._poll_ai():
                need_draw = True
            if self._poll_replay_autoplay():
                need_draw = True

            # A static screen redrawn every frame tears/flickers on Wayland and
            # pins a core — only repaint when something visible changed.
            if (self.thinking or self.dragging is not None or self.toast
                    or self._thought_previous is not None):
                need_draw = True
            if need_draw:
                self._draw()
                self._dirty = False
            self.clock.tick(60)
        if self.progress_store is not None:
            self.progress_store.close()
        pygame.quit()

    def _hover_changed(self, pos):
        btns = self._menu_buttons if self.scene == "menu" else self._game_buttons
        hit = next((i for i, b in enumerate(btns) if b.rect.collidepoint(pos)), None)
        if hit != self._hover:
            self._hover = hit
            return True
        return False

    def _on_key(self, key, modifiers=0):
        if key == pygame.K_n:
            self._change_chess_thought()
            return True
        if key == pygame.K_TAB:
            self._move_button_focus(bool(modifiers & pygame.KMOD_SHIFT))
            return True
        if (key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE)
                and self._button_focus is not None
                and self._activate_button_focus()):
            self._dirty = True
            return True
        if self._button_focus is not None:
            # Global navigation and board keys return input to their scene.
            self._reset_button_focus()
            self._dirty = True
        if key == pygame.K_ESCAPE:
            if self.scene == "game":
                self._to_menu()
                return True
            if self.scene == "replay":
                self._leave_replay()
                return True
            if self.scene == "lesson":
                if self.lesson.state == EXPLORING:
                    self._lesson_return()
                else:
                    self._leave_lesson()
                return True
            if self.menu_view in ("colors", "library", "learn", "play",
                                  "ai_play", "opening_hub", "course",
                                  "course_about"):
                if self.menu_view == "colors":
                    self._close_colors()
                elif self.menu_view == "ai_play":
                    self._open_menu_section("play")
                elif self.menu_view == "course":
                    self._open_menu_section("opening_hub")
                elif self.menu_view == "course_about":
                    self._open_menu_section("course")
                elif self.menu_view == "opening_hub":
                    self._open_menu_section("learn")
                elif self.menu_view in ("learn", "play"):
                    self._open_menu_section("main")
                else:
                    self._close_library()
                return True
            return False
        if self.scene == "menu" and self.menu_view == "library":
            if key == pygame.K_PAGEUP:
                self._change_library_page(-1)
            elif key == pygame.K_PAGEDOWN:
                self._change_library_page(1)
            return True
        if self.scene == "menu" and self.menu_view == "opening_hub":
            if key == pygame.K_PAGEUP:
                self._change_course_page(-1)
            elif key == pygame.K_PAGEDOWN:
                self._change_course_page(1)
            return True
        if self.scene == "replay":
            if key == pygame.K_LEFT:
                self._replay_previous()
            elif key == pygame.K_RIGHT:
                self._replay_next()
            elif key == pygame.K_HOME:
                self._replay_first()
            elif key == pygame.K_END:
                self._replay_last()
            elif key == pygame.K_SPACE:
                self._toggle_replay_autoplay()
            elif key == pygame.K_f:
                self._toggle_flip()
            elif key == pygame.K_PAGEUP:
                self._scroll_replay(-max(1, self.replay_visible_rows - 1))
            elif key == pygame.K_PAGEDOWN:
                self._scroll_replay(max(1, self.replay_visible_rows - 1))
            return True
        if self.scene == "lesson":
            if key == pygame.K_m:
                self._to_menu()
            elif key == pygame.K_f:
                self._toggle_flip()
            elif key == pygame.K_PAGEUP:
                self.lesson_scroll = max(0, self.lesson_scroll - 96)
            elif key == pygame.K_PAGEDOWN:
                self.lesson_scroll = min(
                    self.lesson_max_scroll, self.lesson_scroll + 96)
            elif key == pygame.K_h and self.lesson.state in (QUESTION, FEEDBACK):
                self._lesson_hint()
            elif key == pygame.K_r and self.lesson.state == EXPLORING:
                self._lesson_return()
            else:
                arrows = {pygame.K_UP: (-1, 0), pygame.K_DOWN: (1, 0),
                          pygame.K_LEFT: (0, -1), pygame.K_RIGHT: (0, 1)}
                if key in arrows:
                    self._move_cursor(*arrows[key])
                elif key in (pygame.K_RETURN, pygame.K_KP_ENTER,
                             pygame.K_SPACE):
                    self._activate_cursor()
            self._dirty = True
            return True
        if self.scene != "game":
            return True
        arrows = {pygame.K_UP: (-1, 0), pygame.K_DOWN: (1, 0),
                  pygame.K_LEFT: (0, -1), pygame.K_RIGHT: (0, 1)}
        if key in arrows:
            self._move_cursor(*arrows[key])
        elif key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
            self._activate_cursor()
        elif key == pygame.K_r and not self.thinking:
            self._new_game(self.human_colors)
        elif key == pygame.K_f:
            self._toggle_flip()
        elif key == pygame.K_u:
            self._takeback()
        elif key == pygame.K_s:
            self._save_pgn()
        elif key == pygame.K_l:
            self._load_pgn()
        return True


_PGN_PATH = os.path.join(os.getcwd(), "game.pgn")
