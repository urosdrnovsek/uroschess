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
    portrait_size = min(78 if rect.w < 330 else 92, rect.h - 18)
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
    topic = ((course.card_title or course.title) + " · " +
             (course.opening_name or course.category.replace("_", " ").title()))
    if small_font.size(topic)[0] > width:
        topic = course.card_title or course.title
    topic_font = (small_font if small_font.size(topic)[0] <= width
                  else tag_font)
    subtitle = _fit(topic_font, topic, width)
    surface.blit(topic_font.render(subtitle, True, palette.text),
                 (x, rect.y + 15 + name_font.get_linesize()))
    if progress:
        label = _fit(tag_font, progress, width)
        surface.blit(tag_font.render(label, True, palette.text),
                     (x, rect.bottom - tag_font.get_linesize() - 9))
    if focused:
        draw_focus_ring(surface, rect, palette.accent, 8)


def draw_guide_card(surface, rect, name, portrait, description, palette,
                    title_font, small_font, tag_font, *, hot=False,
                    focused=False):
    """A readable portrait and teaching summary for the Learn gallery."""
    rect = pygame.Rect(rect)
    pygame.draw.rect(surface, palette.btn_hot if hot else palette.btn,
                     rect, border_radius=8)
    pygame.draw.rect(surface, palette.panel_line, rect, width=1,
                     border_radius=8)
    portrait_size = max(38, min(76, rect.h - 12))
    surface.blit(_portrait(portrait, portrait_size, palette.field,
                           palette.text),
                 (rect.x + 8, rect.centery - portrait_size // 2))
    x = rect.x + portrait_size + 19
    width = max(30, rect.right - x - 8)
    compact = rect.h < 80
    title_top = 4 if compact else 7
    title = _fit(title_font, name, width)
    surface.blit(title_font.render(title, True, palette.text),
                 (x, rect.y + title_top))
    words = description.split()
    lines = []
    while words and len(lines) < 2:
        line = words.pop(0)
        while words and small_font.size(line + " " + words[0])[0] <= width:
            line += " " + words.pop(0)
        lines.append(line)
    detail_font = small_font
    detail_y = rect.y + title_top + title_font.get_linesize()
    available = rect.bottom - detail_y - 3
    if available < len(lines) * small_font.get_linesize():
        detail_font = tag_font
    y = detail_y
    for line in lines[:max(0, available // detail_font.get_linesize())]:
        surface.blit(detail_font.render(_fit(detail_font, line, width),
                                        True, palette.text), (x, y))
        y += detail_font.get_linesize()
    if focused:
        draw_focus_ring(surface, rect, palette.accent, 8)
