"""Small shared widgets used by pygame views and controllers."""

import pygame


class Button:
    """A controller-owned button description shared by application views."""

    def __init__(self, rect, label, action, kind="normal", color=None,
                 detail="", value=None):
        self.rect = pygame.Rect(rect)
        self.label = label
        self.action = action
        self.kind = kind
        self.color = color
        self.detail = detail
        self.value = value


def draw_focus_ring(surface, rect, color, radius=8):
    """Draw a high-contrast outer ring for the keyboard-focused control."""

    focus_rect = pygame.Rect(rect).inflate(6, 6)
    pygame.draw.rect(
        surface, color, focus_rect, width=3,
        border_radius=max(0, radius + 3),
    )
