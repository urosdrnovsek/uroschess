"""A small, reusable player portrait and advice card."""

from importlib import resources

import pygame


_PORTRAITS = {}
_PORTRAIT_DISPLAY = None


def _portrait(filename, size, paper, ink):
    global _PORTRAIT_DISPLAY
    display = pygame.display.get_surface()
    if display is not _PORTRAIT_DISPLAY:
        _PORTRAITS.clear()
        _PORTRAIT_DISPLAY = display
    key = (filename, size, paper, ink)
    if key not in _PORTRAITS:
        package = "chess_game.assets.portraits"
        with resources.open_binary(package, filename) as file:
            original = pygame.image.load(file, filename).convert()
        scaled = pygame.transform.smoothscale(original, (size, size))
        pixels = pygame.image.tostring(scaled, "RGB")
        tinted = bytearray(len(pixels))
        for i in range(0, len(pixels), 3):
            lightness = (pixels[i] + pixels[i + 1] + pixels[i + 2]) // 3
            for channel in range(3):
                tinted[i + channel] = (ink[channel] * (255 - lightness)
                                       + paper[channel] * lightness) // 255
        _PORTRAITS[key] = pygame.image.fromstring(
            bytes(tinted), (size, size), "RGB").convert()
    return _PORTRAITS[key]


def _lines(font, text, width):
    result = []
    words = text.split()
    if not words:
        return result
    line = words[0]
    for word in words[1:]:
        candidate = line + " " + word
        if font.size(candidate)[0] <= width:
            line = candidate
        else:
            result.append(line)
            line = word
    result.append(line)
    return result


def draw_chess_thought(surface, rect, thought, title_font, text_font,
                       small_font, palette, compact=False, previous=None,
                       progress=1.0):
    """Draw a theme-coloured portrait card, optionally crossfading from another."""
    rect = pygame.Rect(rect)
    if previous is not None and progress < 1.0:
        eased = progress * progress * (3 - 2 * progress)
        old_card = pygame.Surface(rect.size, pygame.SRCALPHA)
        new_card = pygame.Surface(rect.size, pygame.SRCALPHA)
        local = pygame.Rect((0, 0), rect.size)
        draw_chess_thought(old_card, local, previous, title_font, text_font,
                           small_font, palette, compact)
        draw_chess_thought(new_card, local, thought, title_font, text_font,
                           small_font, palette, compact)
        old_card.set_alpha(round(255 * (1 - eased)))
        new_card.set_alpha(round(255 * eased))
        clip = surface.get_clip()
        surface.set_clip(clip.clip(rect))
        surface.blit(old_card, (rect.x - round(14 * eased), rect.y))
        surface.blit(new_card, (rect.x + round(14 * (1 - eased)), rect.y))
        surface.set_clip(clip)
        return
    paper = palette.field
    ink = palette.text
    edge = palette.panel_line
    pygame.draw.rect(surface, paper, rect, border_radius=10)
    pygame.draw.rect(surface, edge, rect, width=1, border_radius=10)
    if compact:
        portrait_size = min(65, rect.h - 30)
        portrait_x = rect.x + 17
        portrait_y = rect.y + 5
        surface.blit(_portrait(thought.portrait, portrait_size, paper, ink),
                     (portrait_x, portrait_y))
        name = small_font.render(thought.short_name, True, ink)
        surface.blit(name, name.get_rect(
            centerx=portrait_x + portrait_size // 2,
            y=portrait_y + portrait_size))
        quote_x = rect.x + 105
        quote_width = max(40, rect.right - quote_x - 9)
        y = rect.y + 15
        quote = thought.quote
        lines = _lines(text_font, quote, quote_width)
        available = rect.bottom - 3 - y
        if len(lines) * text_font.get_linesize() > available:
            text_font = small_font
            lines = _lines(text_font, quote, quote_width)
        for line in lines:
            if y + text_font.get_linesize() > rect.bottom - 3:
                break
            surface.blit(text_font.render(line, True, ink), (quote_x, y))
            y += text_font.get_linesize()
        return

    portrait_size = min(
        160, rect.w - 24,
        max(72, rect.h - (110 if rect.w >= 300 else 140)))
    portrait_x = rect.centerx - portrait_size // 2
    portrait_y = rect.y + 12
    surface.blit(_portrait(thought.portrait, portrait_size, paper, ink),
                 (portrait_x, portrait_y))
    name = title_font.render(thought.name, True, ink)
    surface.blit(name, name.get_rect(
        centerx=rect.centerx, y=portrait_y + portrait_size + 4))
    y = portrait_y + portrait_size + 37
    for line in _lines(text_font, thought.quote, rect.w - 28):
        if y + text_font.get_linesize() > rect.bottom - 6:
            break
        surface.blit(text_font.render(line, True, ink), (rect.x + 14, y))
        y += text_font.get_linesize()
