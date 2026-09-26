"""Rendering for recorded-game study screens."""

import pygame

from .chess_thought_view import draw_chess_thought
from .widgets import draw_focus_ring


def _round_rect(surface, rect, color, radius):
    rect = pygame.Rect(rect)
    layer = pygame.Surface(rect.size, pygame.SRCALPHA)
    pygame.draw.rect(layer, color, layer.get_rect(), border_radius=radius)
    surface.blit(layer, rect.topleft)


def _outline(surface, rect, color, radius):
    rect = pygame.Rect(rect)
    layer = pygame.Surface(rect.size, pygame.SRCALPHA)
    pygame.draw.rect(layer, (*color, 255), layer.get_rect(), width=1,
                     border_radius=radius)
    surface.blit(layer, rect.topleft)


def _wrap_text(font, text, max_width):
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


def _fit_text(font, text, width):
    if font.size(text)[0] <= width:
        return text
    text = text.rstrip("…")
    while text and font.size(text + "…")[0] > width:
        text = text[:-1]
    return text.rstrip() + "…"


class StudyView:
    """Draw replay information while leaving navigation to its controller."""

    def __init__(self, surface, palette, status_font, text_font, small_font,
                 mono_font, tag_font):
        self.configure(surface, palette, status_font, text_font, small_font,
                       mono_font, tag_font)

    def configure(self, surface, palette, status_font, text_font, small_font,
                  mono_font, tag_font):
        self.surface = surface
        self.palette = palette
        self.status_font = status_font
        self.text_font = text_font
        self.small_font = small_font
        self.mono_font = mono_font
        self.tag_font = tag_font
        self.thought_hit_rect = None
        self.question_rect = None
        self.lesson_content_rect = None
        self.replay_title_rect = None
        self.replay_note_rect = None
        self.replay_moves_rect = None
        self.provenance_rect = None

    def draw_replay_panel(self, rect, replay, entry, mainline, variations,
                          buttons, pointer, focused_button=None, scroll=None,
                          thought=None, thought_previous=None,
                          thought_progress=1.0):
        """Draw replay details and return move hits plus scroll information."""
        p = self.palette
        rect = pygame.Rect(rect)
        radius = p.rounding
        _round_rect(self.surface, rect, (*p.panel, 255), radius)
        _outline(self.surface, rect, p.panel_line, radius)

        if rect.h < 500:
            return self._draw_compact_replay(rect, replay, entry, mainline,
                                             buttons, pointer, focused_button,
                                             scroll)

        x = rect.x + 14
        width = rect.w - 28
        game = replay.game
        header_offset = 114 if thought else 0
        if thought:
            self.thought_hit_rect = pygame.Rect(x, rect.y + 14, width, 100)
            draw_chess_thought(
                self.surface, self.thought_hit_rect, thought,
                self.status_font, self.small_font, self.tag_font, p,
                compact=True, previous=thought_previous,
                progress=thought_progress)
        else:
            self.thought_hit_rect = None
        title_top = y = rect.y + 14 + header_offset
        for line in _wrap_text(self.status_font, entry.title, width):
            self.surface.blit(self.status_font.render(line, True, p.text), (x, y))
            y += self.status_font.get_linesize()
        self.replay_title_rect = pygame.Rect(x, title_top, width, y - title_top)

        players = "{} — {}".format(
            game.headers.get("White", "White"),
            game.headers.get("Black", "Black"),
        )
        y += 5
        for line in _wrap_text(self.small_font, players, width)[:2]:
            self.surface.blit(self.small_font.render(line, True, p.text_dim),
                              (x, y))
            y += self.small_font.get_linesize()
        metadata = "{}  ·  {}  ·  {}".format(
            game.headers.get("Event", "Recorded game"),
            game.headers.get("Date", "?"), game.result)
        for line in _wrap_text(self.tag_font, metadata, width)[:2]:
            self.surface.blit(self.tag_font.render(line, True, p.accent), (x, y))
            y += self.tag_font.get_linesize()

        note_top = max(rect.y + 102 + header_offset, y + 8)
        note_height = 118
        _round_rect(self.surface, (x, note_top, width, note_height),
                    (*p.field, 255), 7)
        self.replay_note_rect = pygame.Rect(x, note_top, width, note_height)
        source = game.source.name if game.source else "Bundled PGN"
        source_text = self.tag_font.render(_fit_text(
            self.tag_font, "SOURCE · " + source, width - 18), True,
                                           p.text_dim)
        self.surface.blit(source_text, (x + 9, note_top + 8))
        comment = replay.current_comment or (
            "No note at this move. Use Previous and Next to continue through "
            "the game.")
        comment_lines = _wrap_text(self.small_font, comment, width - 18)
        note_line_height = self.small_font.get_linesize()
        max_lines = max(1, (note_height - 37) // note_line_height)
        if len(comment_lines) > max_lines:
            comment_lines = comment_lines[:max_lines]
            last = comment_lines[-1]
            comment_lines[-1] = (last[:-1] + "…") if last else "…"
        y = note_top + 28
        for line in comment_lines:
            self.surface.blit(self.small_font.render(line, True, p.text),
                              (x + 9, y))
            y += note_line_height

        moves_top = max(rect.y + (342 if thought else 238),
                        note_top + note_height + 8)
        if len(variations) > 1:
            moves_top += min(3, len(variations)) * 32 + 8
        buttons_top = rect.y + rect.h - 158
        moves_bottom = buttons_top - 10
        move_height = max(40, moves_bottom - moves_top)
        _round_rect(self.surface, (x, moves_top, width, move_height),
                    (*p.field, 255), 7)
        self.replay_moves_rect = pygame.Rect(x, moves_top, width, move_height)

        is_mainline = all(index == 0 for index in replay.path)
        selected_index = replay.ply - 1 if is_mainline else -1
        line_height = max(21, self.mono_font.get_linesize() + 2)
        visible = max(1, (move_height - 12) // line_height)
        max_scroll = max(0, len(mainline) - visible)
        if scroll is None:
            start = max(0, selected_index - visible // 2)
        else:
            start = int(scroll)
        start = max(0, min(start, max_scroll))
        move_hits = []
        y = moves_top + 6
        for index in range(start, min(len(mainline), start + visible)):
            label, _san = mainline[index]
            row = pygame.Rect(x + 6, y - 1, width - 12, line_height)
            if index == selected_index:
                _round_rect(self.surface, row, (*p.accent, 255), 4)
                color = p.on_accent
            else:
                color = p.text
            self.surface.blit(self.mono_font.render(label, True, color),
                              (row.x + 7, y + 1))
            move_hits.append((row, index + 1))
            y += line_height

        if max_scroll:
            track = pygame.Rect(x + width - 6, moves_top + 6,
                                2, move_height - 12)
            pygame.draw.rect(self.surface, p.panel_line, track)
            thumb_h = max(18, int(track.h * visible / len(mainline)))
            thumb_y = track.y + int(
                (track.h - thumb_h) * start / max_scroll)
            pygame.draw.rect(
                self.surface, p.accent,
                (track.x - 1, thumb_y, 4, thumb_h), border_radius=2)

        for index, button in enumerate(buttons):
            hot = button.rect.collidepoint(pointer)
            fill = p.btn_hot if hot else p.btn
            _round_rect(self.surface, button.rect, (*fill, 255), 6)
            _outline(self.surface, button.rect, p.panel_line, 6)
            label = self.small_font.render(button.label, True, p.text)
            self.surface.blit(label, label.get_rect(center=button.rect.center))
            if index == focused_button:
                draw_focus_ring(self.surface, button.rect, p.accent, 6)
        return move_hits, start, max_scroll, visible

    def _draw_compact_replay(self, rect, replay, entry, mainline, buttons,
                             pointer, focused_button, scroll):
        """Keep move notes and all navigation reachable in a stacked layout."""
        p = self.palette
        x, width = rect.x + 14, rect.w - 28
        self.thought_hit_rect = None
        title_top = y = rect.y + 9
        title_lines = _wrap_text(self.status_font, entry.title, width)
        for line in title_lines:
            self.surface.blit(self.status_font.render(line, True, p.text),
                              (x, y))
            y += self.status_font.get_linesize()
        self.replay_title_rect = pygame.Rect(x, title_top, width, y - title_top)
        note = replay.current_comment or "Use Previous and Next to study the game."
        note_lines = _wrap_text(self.small_font, note, width - 12)[
            :1 if len(title_lines) > 1 else 2]
        y += 3
        note_top = y
        for line in note_lines:
            self.surface.blit(self.small_font.render(line, True, p.text_dim),
                              (x + 4, y))
            y += self.small_font.get_linesize()
        self.replay_note_rect = pygame.Rect(x, note_top, width, y - note_top)
        moves_top = y + 4
        button_top = min((button.rect.y for button in buttons),
                         default=rect.bottom - 8)
        move_height = max(22, button_top - moves_top - 5)
        move_rect = pygame.Rect(x, moves_top, width, move_height)
        self.replay_moves_rect = move_rect
        _round_rect(self.surface, move_rect, (*p.field, 255), 6)
        line_height = max(21, self.mono_font.get_linesize() + 2)
        visible = max(1, (move_height - 8) // line_height)
        selected = replay.ply - 1 if all(i == 0 for i in replay.path) else -1
        max_scroll = max(0, len(mainline) - visible)
        start = max(0, min(max_scroll, (selected - visible // 2)
                            if scroll is None else int(scroll)))
        move_hits = []
        for index in range(start, min(len(mainline), start + visible)):
            row = pygame.Rect(x + 5, moves_top + 4 + (index - start) * line_height,
                              width - 10, line_height - 1)
            if index == selected:
                _round_rect(self.surface, row, (*p.accent, 255), 4)
            label = self.mono_font.render(
                mainline[index][0], True,
                p.on_accent if index == selected else p.text)
            self.surface.blit(label, (row.x + 5, row.y + 2))
            move_hits.append((row, index + 1))
        for index, button in enumerate(buttons):
            fill = p.btn_hot if button.rect.collidepoint(pointer) else p.btn
            _round_rect(self.surface, button.rect, (*fill, 255), 6)
            _outline(self.surface, button.rect, p.panel_line, 6)
            label = self.small_font.render(button.label, True, p.text)
            self.surface.blit(label, label.get_rect(center=button.rect.center))
            if index == focused_button:
                draw_focus_ring(self.surface, button.rect, p.accent, 6)
        return move_hits, start, max_scroll, visible

    def draw_lesson_panel(self, rect, lesson, buttons, pointer,
                          scroll=0, transient_message="", focused_button=None,
                          thought=None, thought_previous=None,
                          thought_progress=1.0, show_move_hint=False,
                          coach_label=""):
        """Draw a scrollable guided-lesson panel and return max scroll."""
        p = self.palette
        rect = pygame.Rect(rect)
        radius = p.rounding
        _round_rect(self.surface, rect, (*p.panel, 255), radius)
        _outline(self.surface, rect, p.panel_line, radius)

        x = rect.x + 14
        width = rect.w - 28
        if thought:
            self.thought_hit_rect = pygame.Rect(x, rect.y + 14, width, 100)
            draw_chess_thought(
                self.surface, self.thought_hit_rect, thought,
                self.status_font, self.small_font, self.tag_font, p,
                compact=True, previous=thought_previous,
                progress=thought_progress)
        else:
            self.thought_hit_rect = None
        step = lesson.current_step
        total = len(lesson.resolved_steps)
        title_lines = _wrap_text(
            self.status_font, lesson.lesson.title, width)[:2]
        title_y = (self.thought_hit_rect.bottom + 12
                   if thought else rect.y + 10)
        for line in title_lines:
            self.surface.blit(
                self.status_font.render(line, True, p.text), (x, title_y))
            title_y += self.status_font.get_linesize()
        progress = "STEP {} OF {}".format(lesson.step_index + 1, total)
        progress_y = title_y + 1
        self.surface.blit(self.tag_font.render(progress, True, p.accent),
                          (x, progress_y))

        button_top = min((button.rect.y for button in buttons),
                         default=rect.bottom - 12)
        content_top = progress_y + self.tag_font.get_linesize() + 5
        if lesson.lesson.content_kind == "historical":
            provenance = "FROM A RECORDED GAME"
        else:
            provenance = "PRACTICE POSITION"
        provenance = _fit_text(self.tag_font, provenance, width)
        label = self.tag_font.render(provenance, True, p.text_dim)
        self.surface.blit(label, (x, content_top))
        self.provenance_rect = label.get_rect(topleft=(x, content_top))
        content_top += self.tag_font.get_linesize() + 9
        if step.question and lesson.state in ("READING", "QUESTION", "FEEDBACK"):
            question_top = content_top
            for line in _wrap_text(self.status_font, lesson.active_prompt,
                                   width):
                self.surface.blit(self.status_font.render(line, True, p.text),
                                  (x, content_top))
                content_top += self.status_font.get_linesize()
            content_top += 5
            if show_move_hint and lesson.state == "QUESTION":
                hint = "Tap a piece, then tap a square"
                hint_font = (self.small_font if self.small_font.size(hint)[0]
                             <= width else self.tag_font)
                for line in _wrap_text(hint_font, hint, width):
                    self.surface.blit(hint_font.render(line, True, p.accent),
                                      (x, content_top))
                    content_top += hint_font.get_linesize()
                content_top += 3
            self.question_rect = pygame.Rect(
                x, question_top, width, content_top - question_top)
        else:
            self.question_rect = None
        available_height = max(1, button_top - content_top - 8)
        content = []

        def add(text, font, color, gap=4):
            if not text:
                return
            for line in _wrap_text(font, text, width - 18):
                content.append((line, font, color, gap))

        if lesson.state in ("READING", "QUESTION"):
            if transient_message:
                add("HINT", self.tag_font, p.accent, 5)
                add(transient_message, self.text_font, p.text, 6)
            else:
                add(step.explanation, self.text_font, p.text, 6)
        elif lesson.state == "FEEDBACK":
            if lesson.last_attempt:
                outcome = lesson.last_attempt.outcome
                color = (p.good if outcome in ("preferred", "acceptable")
                         else p.warn if outcome in
                         ("revealed", "not_covered", "continue")
                         else p.bad)
                add(lesson.last_attempt.feedback, self.text_font, color, 6)
            if transient_message:
                add(transient_message, self.text_font, p.warn, 5)
        elif lesson.state == "EXPLORING":
            add("Try any legal move. Use Back to lesson when you are ready.",
                self.text_font, p.text, 6)
        elif lesson.state == "COMPLETED":
            add(lesson.lesson.takeaway, self.text_font, p.text, 6)

        line_heights = [font.get_linesize() + gap
                        for _line, font, _color, gap in content]
        natural_height = sum(line_heights) + 16
        content_rect = pygame.Rect(
            x, content_top, width,
            min(available_height, max(44, natural_height)))
        self.lesson_content_rect = content_rect
        full_height = max(content_rect.h, natural_height)
        body = pygame.Surface((content_rect.w, full_height), pygame.SRCALPHA)
        y = 8
        for (line, font, color, gap), height in zip(content, line_heights):
            body.blit(font.render(line, True, color), (9, y))
            y += height
        max_scroll = max(0, full_height - content_rect.h)
        scroll = max(0, min(int(scroll), max_scroll))
        _round_rect(self.surface, content_rect, (*p.field, 255), 7)
        old_clip = self.surface.get_clip()
        self.surface.set_clip(content_rect)
        self.surface.blit(body, (content_rect.x, content_rect.y - scroll))
        self.surface.set_clip(old_clip)
        if max_scroll and content_rect.h >= 20:
            track = pygame.Rect(content_rect.right - 4, content_rect.y + 5,
                                2, content_rect.h - 10)
            pygame.draw.rect(self.surface, p.panel_line, track)
            thumb_h = max(18, int(track.h * content_rect.h / full_height))
            thumb_y = track.y + int((track.h - thumb_h) * scroll / max_scroll)
            pygame.draw.rect(self.surface, p.accent,
                             (track.x - 1, thumb_y, 4, thumb_h),
                             border_radius=2)

        for index, button in enumerate(buttons):
            hot = button.rect.collidepoint(pointer)
            fill = (p.accent if button.kind == "cta" else
                    p.btn_hot if hot else p.btn)
            _round_rect(self.surface, button.rect, (*fill, 255), 6)
            _outline(self.surface, button.rect, p.panel_line, 6)
            label = self.small_font.render(
                button.label, True,
                p.on_accent if button.kind == "cta" else p.text)
            self.surface.blit(label, label.get_rect(center=button.rect.center))
            if index == focused_button:
                draw_focus_ring(self.surface, button.rect, p.accent, 6)
        return max_scroll
