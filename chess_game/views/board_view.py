"""Reusable rendering and coordinate mapping for a supplied board position."""

import math

import pygame

from ..pieces import BLACK, GLYPHS, LETTERS, WHITE


def _luma(color):
    return 0.299 * color[0] + 0.587 * color[1] + 0.114 * color[2]


def _outline_for(color):
    return (22, 18, 16) if _luma(color) > 120 else (240, 235, 229)


def _text_for(color):
    return (18, 16, 14) if _luma(color) > 120 else (250, 248, 244)


class BoardView:
    """Draw any board state without owning game or lesson state.

    The caller controls the surface, geometry, colors, and overlays. This keeps
    replay and lesson controllers independent from ordinary game flow.
    """

    def __init__(self, surface, x, y, square_size, piece_font, fallback_font,
                 use_glyphs=True, flipped=False):
        self._shadow = None
        self._shadow_size = None
        self.configure(surface, x, y, square_size, piece_font, fallback_font,
                       use_glyphs=use_glyphs, flipped=flipped)

    def configure(self, surface, x, y, square_size, piece_font, fallback_font,
                  use_glyphs=True, flipped=False):
        self.surface = surface
        self.x = int(x)
        self.y = int(y)
        self.square_size = int(square_size)
        self.piece_font = piece_font
        self.fallback_font = fallback_font
        self.use_glyphs = bool(use_glyphs)
        self.flipped = bool(flipped)
        if self._shadow_size != self.square_size:
            self._build_shadow()

    @property
    def pixel_size(self):
        return self.square_size * 8

    def _build_shadow(self):
        width = max(4, int(self.square_size * 0.80))
        height = max(4, int(self.square_size * 0.30))
        small = pygame.Surface((max(4, width // 3), max(4, height // 3)),
                               pygame.SRCALPHA)
        pygame.draw.ellipse(small, (0, 0, 0, 110), small.get_rect())
        self._shadow = pygame.transform.smoothscale(small, (width, height))
        self._shadow_size = self.square_size

    def square_to_pixel(self, square):
        row, column = square
        if self.flipped:
            row, column = 7 - row, 7 - column
        return (self.x + column * self.square_size,
                self.y + row * self.square_size)

    def pixel_to_square(self, position):
        x = position[0] - self.x
        y = position[1] - self.y
        if not (0 <= x < self.pixel_size and 0 <= y < self.pixel_size):
            return None
        row = int(y // self.square_size)
        column = int(x // self.square_size)
        if self.flipped:
            row, column = 7 - row, 7 - column
        return row, column

    def draw_base(self, light=(238, 218, 181), dark=(139, 99, 68)):
        """Draw a simple board base for standalone study/rendering screens."""
        for row in range(8):
            for column in range(8):
                color = light if (row + column) % 2 == 0 else dark
                pygame.draw.rect(
                    self.surface,
                    color,
                    (self.x + column * self.square_size,
                     self.y + row * self.square_size,
                     self.square_size,
                     self.square_size),
                )

    def tint(self, square, color, alpha=150):
        x, y = self.square_to_pixel(square)
        overlay = pygame.Surface((self.square_size, self.square_size),
                                 pygame.SRCALPHA)
        overlay.fill((*color, alpha))
        self.surface.blit(overlay, (x, y))

    @staticmethod
    def algebraic_to_square(name):
        if (not isinstance(name, str) or len(name) != 2
                or name[0] not in "abcdefgh" or name[1] not in "12345678"):
            raise ValueError("invalid chess square: {!r}".format(name))
        return 8 - int(name[1]), ord(name[0]) - ord("a")

    def _draw_lesson_highlights(self, highlights):
        colors = {
            "focus": (55, 170, 230, 190),
            "target": (70, 190, 105, 205),
            "warning": (225, 75, 70, 205),
        }
        for item in highlights:
            square = self.algebraic_to_square(item.square)
            x, y = self.square_to_pixel(square)
            color = colors.get(item.role, colors["focus"])
            overlay = pygame.Surface((self.square_size, self.square_size),
                                     pygame.SRCALPHA)
            inset = max(3, self.square_size // 14)
            width = max(3, self.square_size // 14)
            pygame.draw.rect(
                overlay, color,
                (inset, inset, self.square_size - inset * 2,
                 self.square_size - inset * 2),
                width=width, border_radius=max(4, self.square_size // 9))
            if item.role == "warning":
                pad = max(10, self.square_size // 4)
                pygame.draw.line(overlay, color, (pad, pad),
                                 (self.square_size - pad, self.square_size - pad),
                                 max(2, width // 2))
                pygame.draw.line(overlay, color,
                                 (self.square_size - pad, pad),
                                 (pad, self.square_size - pad),
                                 max(2, width // 2))
            self.surface.blit(overlay, (x, y))

    def _draw_lesson_arrows(self, arrows):
        colors = {
            "idea": (70, 165, 225, 205),
            "move": (75, 190, 105, 220),
            "warning": (225, 75, 70, 215),
        }
        overlay = pygame.Surface(self.surface.get_size(), pygame.SRCALPHA)
        for item in arrows:
            start = self.algebraic_to_square(item.from_square)
            end = self.algebraic_to_square(item.to_square)
            sx, sy = self.square_to_pixel(start)
            ex, ey = self.square_to_pixel(end)
            start_point = (sx + self.square_size / 2,
                           sy + self.square_size / 2)
            end_point = (ex + self.square_size / 2,
                         ey + self.square_size / 2)
            dx = end_point[0] - start_point[0]
            dy = end_point[1] - start_point[1]
            length = math.hypot(dx, dy)
            if not length:
                continue
            ux, uy = dx / length, dy / length
            head = max(11, int(self.square_size * 0.24))
            line_end = (end_point[0] - ux * head * 0.65,
                        end_point[1] - uy * head * 0.65)
            color = colors.get(item.role, colors["idea"])
            width = max(5, self.square_size // 10)
            pygame.draw.line(overlay, color, start_point, line_end, width)
            perpendicular = (-uy, ux)
            points = [
                end_point,
                (end_point[0] - ux * head + perpendicular[0] * head * 0.55,
                 end_point[1] - uy * head + perpendicular[1] * head * 0.55),
                (end_point[0] - ux * head - perpendicular[0] * head * 0.55,
                 end_point[1] - uy * head - perpendicular[1] * head * 0.55),
            ]
            pygame.draw.polygon(overlay, color, points)
            pygame.draw.circle(overlay, color,
                               (int(start_point[0]), int(start_point[1])),
                               max(3, width // 2), 2)
        self.surface.blit(overlay, (0, 0))

    def draw_piece(self, piece, center, white_color, black_color):
        color, piece_type = piece[0], piece[1]
        fill = white_color if color == WHITE else black_color
        if self.use_glyphs:
            glyph = GLYPHS[piece_type]
            outline = _outline_for(fill)
            for dx, dy in ((-2, 0), (2, 0), (0, -2), (0, 2)):
                image = self.piece_font.render(glyph, True, outline)
                self.surface.blit(
                    image, image.get_rect(center=(center[0] + dx, center[1] + dy)))
            image = self.piece_font.render(glyph, True, fill)
            self.surface.blit(image, image.get_rect(center=center))
            return

        radius = max(10, int(self.piece_font.get_height() * 0.42))
        pygame.draw.circle(self.surface, fill, center, radius)
        pygame.draw.circle(self.surface, _outline_for(fill), center, radius, 2)
        label = self.fallback_font.render(LETTERS[piece_type], True, _text_for(fill))
        self.surface.blit(label, label.get_rect(center=center))

    def draw_position(self, board, *, white_color, black_color, last_move=None,
                      selected=None, legal_destinations=(), cursor=None,
                      checked_squares=(), dragging=None, drag_position=(0, 0),
                      lesson_highlights=(), lesson_arrows=(),
                      selection_color=(230, 190, 40),
                      last_move_color=(80, 130, 210),
                      check_color=(210, 50, 50), legal_color=(0, 0, 0, 70),
                      cursor_color=(80, 160, 230)):
        """Draw position pieces and optional interaction overlays."""
        if last_move:
            self.tint(last_move.frm, last_move_color)
            self.tint(last_move.to, last_move_color)
        if selected is not None:
            self.tint(selected, selection_color, 170)
        for square in checked_squares:
            if square is not None:
                self.tint(square, check_color)
        self._draw_lesson_highlights(lesson_highlights)

        for square, is_capture in legal_destinations:
            x, y = self.square_to_pixel(square)
            dot = pygame.Surface((self.square_size, self.square_size), pygame.SRCALPHA)
            center = self.square_size // 2, self.square_size // 2
            if is_capture:
                pygame.draw.circle(dot, legal_color, center,
                                   self.square_size // 2 - 3, 5)
            else:
                pygame.draw.circle(dot, legal_color, center,
                                   max(6, self.square_size // 7))
            self.surface.blit(dot, (x, y))

        if cursor is not None:
            x, y = self.square_to_pixel(cursor)
            pygame.draw.rect(self.surface, cursor_color,
                             (x + 1, y + 1,
                              self.square_size - 2, self.square_size - 2), 3)

        for row in range(8):
            for column in range(8):
                piece = board.grid[row][column]
                if not piece:
                    continue
                if dragging and dragging[0] == (row, column) and dragging[2]:
                    continue
                x, y = self.square_to_pixel((row, column))
                self.surface.blit(
                    self._shadow,
                    (x + (self.square_size - self._shadow.get_width()) // 2 + 2,
                     y + int(self.square_size * 0.60)),
                )
                center = x + self.square_size // 2, y + self.square_size // 2
                self.draw_piece(piece, center, white_color, black_color)

        if dragging and dragging[2]:
            piece = dragging[1]
            x, y = drag_position
            large_shadow = pygame.transform.smoothscale(
                self._shadow,
                (int(self._shadow.get_width() * 1.35),
                 int(self._shadow.get_height() * 1.35)),
            )
            self.surface.blit(
                large_shadow,
                (x - large_shadow.get_width() // 2 + 10,
                 y - large_shadow.get_height() // 2 + 26),
            )
            self.draw_piece(piece, (x, y), white_color, black_color)

        self._draw_lesson_arrows(lesson_arrows)
