"""Portrait cards for player opening courses."""

import pygame

from .chess_thought_view import _portrait
from .widgets import draw_focus_ring


def _fit(font, value, width):
    if font.size(value)[0] <= width:
        return value
    while value and font.size(value + "…")[0] > width:
        value = value[:-1]
    return value + "…"


def draw_player_card(surface, rect, player, course, palette, title_font,
                     small_font, tag_font, *, hot=False, focused=False,
                     progress=""):
    rect = pygame.Rect(rect)
    fill = palette.btn_hot if hot else palette.btn
    pygame.draw.rect(surface, fill, rect, border_radius=8)
    pygame.draw.rect(surface, palette.panel_line, rect, width=1,
                     border_radius=8)
    portrait_size = min(68 if rect.w < 330 else 78, rect.h - 20)
    portrait_x = rect.x + 12
    portrait_y = rect.y + (rect.h - portrait_size) // 2
    surface.blit(_portrait(player.portrait, portrait_size,
                           palette.field, palette.text),
                 (portrait_x, portrait_y))
    x = portrait_x + portrait_size + 13
    width = max(40, rect.right - x - 10)
    name_font = (title_font if title_font.size(player.name)[0] <= width
                 else small_font)
    name = _fit(name_font, player.name, width)
    surface.blit(name_font.render(name, True, palette.text),
                 (x, rect.y + 11))
    topic = (course.card_title or course.title) + " · " + course.opening_name
    if small_font.size(topic)[0] > width:
        topic = course.card_title or course.title
    topic_font = (small_font if small_font.size(topic)[0] <= width
                  else tag_font)
    subtitle = _fit(topic_font, topic, width)
    surface.blit(topic_font.render(subtitle, True, palette.accent),
                 (x, rect.y + 15 + name_font.get_linesize()))
    if progress:
        label = _fit(tag_font, progress, width)
        surface.blit(tag_font.render(label, True, palette.text_dim),
                     (x, rect.bottom - tag_font.get_linesize() - 9))
    if focused:
        draw_focus_ring(surface, rect, palette.accent, 8)
