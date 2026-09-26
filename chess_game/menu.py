"""Menu hierarchy and responsive menu control geometry."""

import pygame

from .views.widgets import Button
from .pieces import WHITE, BLACK


DIFFICULTIES = [
    ("Easy", 0.25, 2),
    ("Normal", 1.0, 64),
    ("Hard", 2.5, 64),
    ("Max", 6.0, 64),
]

BOARD_STYLE_NAMES = ["Theme", "Wood", "Marble", "Emerald", "Ocean"]

WHITE_PRESETS = [
    (250, 250, 250), (240, 222, 186), (206, 224, 240),
    (255, 176, 210), (176, 232, 200), (238, 206, 110),
]
BLACK_PRESETS = [
    (32, 28, 26), (74, 46, 34), (30, 52, 112),
    (112, 32, 58), (28, 74, 52), (92, 60, 142),
]
TEXT_SIZES = [
    ("Standard", 1.0),
    ("Large", 1.2),
    ("Extra large", 1.4),
]

class MenuLayoutMixin:
    """Build menu controls while the UI owns their actions and state."""

    def _study_menu_top(self):
        """Leave room for the card and its navigation at shorter heights."""
        return max(20, min(145, self.win_h - 500))

    def _build_menu_buttons(self):
        self._menu_buttons = []
        self._menu_heads = []
        if self.menu_view == "colors":
            self._build_menu_colors()
        elif self.menu_view == "library":
            self._build_menu_library()
        elif self.menu_view == "opening_hub":
            self._build_opening_hub()
        elif self.menu_view == "course":
            self._build_course_menu()
        elif self.menu_view == "course_about":
            self._build_course_about()
        elif self.menu_view in ("learn", "play", "ai_play"):
            self._build_menu_section()
        else:
            self._build_menu_main()
        card = self._menu_card
        gap = (40 if self.menu_view == "main" and card.top >= 175
               else 28 if card.top >= 136 else 16)
        portrait_height = min(100, card.top - 8 - gap)
        portrait_width = min(472, card.w)
        self._feature_rect = pygame.Rect(
            card.centerx - portrait_width // 2,
            card.top - gap - portrait_height,
            portrait_width, portrait_height)

    def _build_menu_main(self):
        card_width = min(472, self.win_w - 24)
        left = (self.win_w - card_width) // 2
        top = max(95, min(225, self.win_h - 410))
        card = pygame.Rect(left, top, card_width, 294)
        self._menu_card = card
        x, w = card.x + 24, card.w - 48
        cx = card.centerx
        self._menu_heads.append(("CHOOSE AN ACTIVITY", x, card.y + 17))
        for index, (label, action) in enumerate((
                ("Learn", lambda: self._open_menu_section("learn")),
                ("Play", lambda: self._open_menu_section("play")),
                ("Watch games", lambda: self._open_library("replay")))):
            self._menu_buttons.append(Button(
                (x, card.y + 44 + index * 59, w, 49), label, action,
                kind="cta" if index == 0 else "step"))
        self._menu_buttons.append(
            Button((cx - min(200, w // 2), card.bottom + 8,
                    min(400, w), 38), "Appearance",
                   self._open_colors, kind="cta"))
        self._menu_buttons.append(
            Button((cx - min(200, w // 2), card.bottom + 50,
                    min(400, w), 36), "Exit",
                   self._exit, kind="exit"))

    def _open_menu_section(self, section):
        self._reset_button_focus()
        self.menu_view = section
        self._menu_buttons = []
        self._change_chess_thought(play_sound=False)

    def _build_menu_section(self):
        width = min(472, self.win_w - 24)
        top = max(95, min(190, self.win_h - 490))
        card = pygame.Rect((self.win_w - width) // 2, top, width, 390)
        self._menu_card = card
        x, w = card.x + 24, card.w - 48
        gap, half = 8, (w - 8) // 2
        if self.menu_view == "learn":
            self._menu_heads.append(("LEARN CHESS", x, top + 16))
            items = (
                ("Continue lesson" if self._resume_entry() else "Start learning",
                 self._continue_learning),
                ("Your lesson path", lambda: self._open_library("path")),
                ("Openings", self._open_openings),
                ("Endgames", lambda: self._open_library("endgame")),
                ("Guided games", lambda: self._open_library("guided_game")),
            )
            for i, (label, action) in enumerate(items):
                self._menu_buttons.append(Button(
                    (x, top + 43 + i * 55, w, 45), label, action,
                    kind="cta" if i == 0 else "step"))
            if self._has_learn_browse():
                self._menu_buttons.append(Button(
                    (x, top + 318, w, 45), "Return to last course or list",
                    self._restore_learn_browse, kind="step"))
        elif self.menu_view == "play":
            self._menu_heads.append(("PLAY CHESS", x, top + 16))
            self._menu_buttons.append(Button(
                (x, top + 45, w, 48), "Play against AI",
                lambda: self._open_menu_section("ai_play"), kind="cta"))
            self._menu_buttons.append(Button(
                (x, top + 103, w, 48), "Two players",
                lambda: self.start_game({WHITE, BLACK}), kind="step"))
        else:
            self._menu_heads.append(("PLAY AGAINST AI", x, top + 16))
            for i, (label, colors) in enumerate((
                    ("Play as White", {WHITE}),
                    ("Play as Black", {BLACK}),
                    ("Watch AI vs AI", set()))):
                self._menu_buttons.append(Button(
                    (x, top + 42 + i * 48, w, 40), label,
                    lambda c=colors: self.start_game(c), kind="step"))
            name, _time, _depth = DIFFICULTIES[self.difficulty]
            self._menu_heads.append(("AI DIFFICULTY: " + name, x, top + 199))
            for i, (label, delta) in enumerate((("‹  Easier", -1),
                                                 ("Harder  ›", 1))):
                self._menu_buttons.append(Button(
                    (x + i * (half + gap), top + 222, half, 38), label,
                    lambda d=delta: self._cycle_difficulty(d), kind="step"))
        self._menu_buttons.append(Button(
            (x, card.bottom + 8, w, 38), "‹  Back",
            lambda: self._open_menu_section(
                "play" if self.menu_view == "ai_play" else "main"),
            kind="cta"))

    def _build_opening_hub(self):
        width = min(660, self.win_w - 24)
        top = self._study_menu_top()
        card = pygame.Rect((self.win_w - width) // 2, top, width, 430)
        self._menu_card = card
        x, inner = card.x + 22, card.w - 44
        self._menu_heads.append(("OPENINGS", x, top + 16))
        basics = self.game_library.lesson_entry("opening-essentials")
        if basics:
            self._menu_buttons.append(Button(
                (x, top + 40, inner, 66), "Opening basics",
                lambda: self.start_lesson(basics), kind="library",
                detail="Start here · centre and development"))
        self._menu_heads.append(("PRACTISE WITH ANIMAL COACHES",
                                 x, top + 124))
        courses = (self.game_library.courses_for_category("opening")
                   if self.game_library else ())
        page_count = max(1, (len(courses) + 1) // 2)
        self.course_page = max(0, min(self.course_page, page_count - 1))
        page_courses = courses[self.course_page * 2:self.course_page * 2 + 2]
        for index, course in enumerate(page_courses):
            self._menu_buttons.append(Button(
                (x, top + 150 + index * 119, inner, 106),
                course.title, lambda ident=course.course_id:
                self._open_course(ident), kind="player", value=course.course_id))
        last = top + 150 + len(page_courses) * 119
        self._menu_buttons.append(Button(
            (x, min(last + 7, card.bottom - 48), inner, 38),
            "All opening lessons", lambda: self._open_library("opening"),
            kind="step"))
        if page_count > 1:
            gap = 8
            side = (inner - 2 * gap) // 3
            center = inner - 2 * side - 2 * gap
            for index, (label, action, button_width) in enumerate((
                    ("‹ Prev", lambda: self._change_course_page(-1), side),
                    ("Back", lambda: self._open_menu_section("learn"), center),
                    ("Next ›", lambda: self._change_course_page(1), side))):
                bx = x + (0 if index == 0 else
                          side + gap if index == 1 else
                          side + gap + center + gap)
                self._menu_buttons.append(Button(
                    (bx, card.bottom + 8, button_width, 38), label, action,
                    kind="cta" if index == 1 else "step"))
        else:
            self._menu_buttons.append(Button(
                (x, card.bottom + 8, inner, 38), "‹  Back",
                lambda: self._open_menu_section("learn"), kind="cta"))

    def _build_course_menu(self):
        course = (self.game_library.course(self.active_course_id)
                  if self.game_library else None)
        if course is None:
            self._build_opening_hub()
            return
        width = min(660, self.win_w - 24)
        top = self._study_menu_top()
        card = pygame.Rect((self.win_w - width) // 2, top, width, 430)
        self._menu_card = card
        x, inner = card.x + 22, card.w - 44
        self._menu_heads.append((course.opening_name.upper() + " WITH " +
                                 self.game_library.player(course.player_id).short_name.upper(),
                                 x, top + 16))
        self._course_profile_rect = pygame.Rect(x, top + 42, inner, 100)
        entries = self.game_library.course_lessons(course)
        missing_basics = self._course_missing_prerequisites(course)
        complete = bool(entries) and all(
            self._course_entry_status(entry) in ("DONE", "REVISIT")
            for entry in entries)
        self._menu_heads.append(("PRACTISE BASICS FIRST · OR TRY A LESSON"
                                 if missing_basics else
                                 "COURSE COMPLETE · PRACTISE AGAIN"
                                 if complete else "LESSONS BY UROSCHESS",
                                 x, top + 151))
        for index, entry in enumerate(entries[:3]):
            status = self._course_entry_status(entry)
            detail = ("LATER · Try earlier lesson first" if status == "LATER"
                      else "{}  ·  {} min  ·  Practice position".format(
                          status, entry.lesson.estimated_minutes))
            self._menu_buttons.append(Button(
                (x, top + 175 + index * 70, inner, 62),
                entry.lesson.title,
                lambda item=entry: self.start_lesson(
                    item, course_id=course.course_id),
                kind="library", detail=detail))
        started = any(self._course_entry_status(entry) in
                      ("IN PROGRESS", "DONE", "REVISIT") for entry in entries)
        if started and missing_basics:
            half = (inner - 8) // 2
            self._menu_buttons.append(Button(
                (x, card.bottom - 42, half, 36),
                "Basics" if inner < 380 else "Practise basics",
                self._practise_course_basics, kind="step"))
            self._menu_buttons.append(Button(
                (x + half + 8, card.bottom - 42, inner - half - 8, 36),
                ("Review" if complete else "Continue") if inner < 380
                else ("Review last lesson" if complete else "Continue course"),
                self._continue_course, kind="cta"))
        elif missing_basics:
            self._menu_buttons.append(Button(
                (x, card.bottom - 42, inner, 36), "Practise basics",
                self._practise_course_basics, kind="cta"))
        elif started:
            self._menu_buttons.append(Button(
                (x, card.bottom - 42, inner, 36),
                "Review last lesson" if complete else "Continue course",
                self._continue_course, kind="cta"))
        half = (inner - 8) // 2
        self._menu_buttons.append(Button(
            (x, card.bottom + 8, half, 38), "‹  Back",
            lambda: self._open_menu_section("opening_hub"), kind="cta"))
        self._menu_buttons.append(Button(
            (x + half + 8, card.bottom + 8, inner - half - 8, 38),
            "Sources", self._open_course_about, kind="step"))

    def _build_course_about(self):
        course = self.game_library.course(self.active_course_id)
        if course is None:
            self._build_opening_hub()
            return
        width = min(660, self.win_w - 24)
        top = self._study_menu_top()
        card = pygame.Rect((self.win_w - width) // 2, top, width, 430)
        self._menu_card = card
        x, inner = card.x + 22, card.w - 44
        player = self.game_library.player(course.player_id)
        self._menu_heads.extend((
            ("ABOUT THIS COURSE", x, top + 16),
            ("LESSONS BY UROSCHESS", x, top + 49),
            ("OPENING BACKGROUND", x, top + 116),
            ("ARCHIVAL GAME", x, top + 172),
            ("PORTRAIT CREDIT", x, top + 237),
        ))
        self._course_about_rect = pygame.Rect(x, top + 35, inner, 225)
        self._menu_buttons.extend((
            Button((x, top + 297, inner, 36), "Read opening source",
                   lambda: self._open_source_link(course.association_source.url),
                   kind="step"),
            Button((x, top + 343, inner, 36), "Watch archival game",
                   self._watch_course_source, kind="cta", value="source_game"),
            Button((x, card.bottom + 8, inner, 38), "‹  Back to course",
                   lambda: self._open_menu_section("course"), kind="cta"),
        ))

    def _build_menu_library(self):
        cx = self.win_w // 2
        top = self._study_menu_top()
        card_width = min(660, self.win_w - 24)
        card = pygame.Rect(cx - card_width // 2, top, card_width, 430)
        self._menu_card = card
        x, width = card.x + 28, card.w - 56
        section = {
            "path": "YOUR LESSON PATH",
            "guided_game": "GUIDED GAME LIBRARY",
            "opening": "OPENING LESSONS",
            "endgame": "ENDGAME LESSONS",
            "replay": "FULL GAMES TO STUDY",
        }.get(self.library_filter, "LESSONS")
        if self.win_w < 500:
            section = {
                "path": "LESSON PATH", "guided_game": "GUIDED GAMES",
                "opening": "OPENINGS", "endgame": "ENDGAMES",
                "replay": "WATCH GAMES",
            }.get(self.library_filter, "LESSONS")
        entries = self._library_entries()
        page_size = 5
        page_count = max(1, (len(entries) + page_size - 1) // page_size)
        self.library_page = max(0, min(self.library_page, page_count - 1))
        if page_count > 1:
            section += ("  ·  {}/{}" if self.win_w < 500
                        else "  ·  PAGE {} OF {}").format(
                            self.library_page + 1, page_count)
        self._menu_heads.append((section, x, card.y + 22))
        y = card.y + 50
        start = self.library_page * page_size
        for entry in entries[start:start + page_size]:
            game = entry.game
            players = "{} — {}".format(
                game.headers.get("White", "White"), game.headers.get("Black", "Black"))
            detail = "{}  ·  {}  ·  {}".format(
                players, entry.level, game.headers.get("Date", "unknown date"))
            if self.library_filter == "replay":
                white = game.headers.get("White", "White")
                black = game.headers.get("Black", "Black")
                white = white.split(",")[0].split()[-1]
                black = black.split(",")[0].split()[-1]
                year = game.headers.get("Date", "unknown date")[:4]
                replay_detail = "{} vs {}  ·  {}  ·  {}".format(
                    white, black, entry.level.capitalize(), year)
                self._menu_buttons.append(Button(
                    (x, y, width, 66), entry.title,
                    lambda item=entry: self.start_replay(item),
                    kind="library", detail=replay_detail,
                    value=game.game_id))
                y += 76
            elif entry.lesson:
                if self.library_filter == "path":
                    lesson_detail = "{}  ·  {} min  ·  {}".format(
                        self._path_status(entry),
                        entry.lesson.estimated_minutes, entry.level)
                elif entry.category == "guided_game":
                    lesson_detail = "Guided lesson  ·  {} min  ·  {}".format(
                        entry.lesson.estimated_minutes, detail)
                else:
                    kind = ("Opening practice" if entry.category == "opening"
                            else "Endgame practice")
                    lesson_detail = "{}  ·  {} min  ·  {}".format(
                        kind, entry.lesson.estimated_minutes, entry.level)
                self._menu_buttons.append(Button(
                    (x, y, width, 66), entry.lesson.title,
                    lambda item=entry: self.start_lesson(item),
                    kind="library", detail=lesson_detail))
                y += 72
            else:
                self._menu_buttons.append(Button(
                    (x, y, width, 66), entry.title,
                    lambda item=entry: self.start_replay(item),
                    kind="library", detail=detail))
                y += 76
        if page_count > 1:
            gap = 8
            nav_width = card.w - 56
            side = (nav_width - 2 * gap) // 3
            center = nav_width - 2 * side - 2 * gap
            nav_x = card.x + 28
            compact_nav = self.win_w < 660
            self._menu_buttons.append(Button(
                (nav_x, card.bottom + 18, side, 44),
                "‹ Prev" if compact_nav else "‹  Previous page",
                lambda: self._change_library_page(-1), kind="step"))
            self._menu_buttons.append(Button(
                (nav_x + side + gap, card.bottom + 18, center, 44),
                "Back" if compact_nav else "‹  Back",
                self._close_library, kind="cta"))
            self._menu_buttons.append(Button(
                (nav_x + side + gap + center + gap, card.bottom + 18,
                 side, 44),
                "Next ›" if compact_nav else "Next page  ›",
                lambda: self._change_library_page(1), kind="step"))
        else:
            self._menu_buttons.append(
                Button((cx - min(110, card.w // 3), card.bottom + 18,
                        min(220, 2 * card.w // 3), 44), "‹  Back",
                       self._close_library, kind="cta"))

    def _build_menu_colors(self):
        cx = self.win_w // 2
        if self.win_w < 700:
            width = min(420, self.win_w - 24)
            height = min(530, self.win_h - 112)
            top = max(30, (self.win_h - height - 52) // 2)
            card = pygame.Rect(cx - width // 2, top, width, height)
            self._menu_card = card
            x, inner = card.x + 18, card.w - 36
            sw = (inner - 9) // 2
            self._menu_heads.append(("BOARD STYLE", x, top + 13))
            for i, name in enumerate(BOARD_STYLE_NAMES):
                self._menu_buttons.append(Button(
                    (x + i % 2 * (sw + 9), top + 34 + i // 2 * 39,
                     sw, 34), name, lambda n=name: self._set_style(n),
                    kind="style"))
            self._menu_heads.append(("PREVIEW", x, top + 116))
            self._preview_rect = pygame.Rect(x, top + 138, inner, 90)
            self._menu_heads.append(("WHITE PIECES", x, top + 238))
            swatch = min(40, (inner - 5 * 6) // 6)
            for i, col in enumerate(WHITE_PRESETS):
                self._menu_buttons.append(Button(
                    (x + i * (swatch + 6), top + 257, swatch, 34), "",
                    lambda c=col: self._set_white(c), kind="swatchW", color=col))
            self._menu_heads.append(("BLACK PIECES", x, top + 298))
            for i, col in enumerate(BLACK_PRESETS):
                self._menu_buttons.append(Button(
                    (x + i * (swatch + 6), top + 317, swatch, 34), "",
                    lambda c=col: self._set_black(c), kind="swatchB", color=col))
            self._menu_heads.append(("TEXT SIZE", x, top + 358))
            size_w = (inner - 12) // 3
            for i, (label, scale) in enumerate(TEXT_SIZES):
                short_label = ("Standard", "Large", "XL")[i]
                if self.win_w < 400:
                    short_label = ("Std", "Large", "XL")[i]
                self._menu_buttons.append(Button(
                    (x + i * (size_w + 6), top + 379, size_w, 34), short_label,
                    lambda value=scale: self._set_text_scale(value),
                    kind="textsize", value=scale))
            self._menu_heads.append(("SOUND", x, top + 423))
            self._menu_buttons.append(Button(
                (x, top + 442, inner, 34),
                "Sound on" if self.sound_enabled else "Sound off",
                self._toggle_sound, kind="toggle", value=self.sound_enabled))
            self._menu_buttons.append(Button(
                (x, card.bottom + 8, inner, 38), "‹  Back",
                self._close_colors, kind="cta"))
            return
        top = max(140, self.win_h // 2 - 230)
        card = pygame.Rect(cx - 322, top, 644, 478)
        self._menu_card = card
        lx = card.x + 28
        rx = cx + 26
        rw = card.right - 28 - rx

        self._menu_heads.append(("BOARD  STYLE", lx, card.y + 22))
        sw = 142
        for i, name in enumerate(BOARD_STYLE_NAMES):
            bx = lx + (i % 2) * (sw + 12)
            by = card.y + 46 + (i // 2) * 50
            self._menu_buttons.append(
                Button((bx, by, sw, 40), name,
                       lambda n=name: self._set_style(n), kind="style"))
        self._menu_heads.append(("PREVIEW", lx, card.y + 208))
        self._preview_rect = pygame.Rect(lx, card.y + 230, sw * 2 + 12, 176)

        gap = (rw - 6 * 40) // 5
        self._menu_heads.append(("WHITE  PIECES", rx, card.y + 22))
        for i, col in enumerate(WHITE_PRESETS):
            self._menu_buttons.append(
                Button((rx + i * (40 + gap), card.y + 46, 40, 40), "",
                       lambda c=col: self._set_white(c), kind="swatchW", color=col))
        self._menu_heads.append(("BLACK  PIECES", rx, card.y + 118))
        for i, col in enumerate(BLACK_PRESETS):
            self._menu_buttons.append(
                Button((rx + i * (40 + gap), card.y + 142, 40, 40), "",
                       lambda c=col: self._set_black(c), kind="swatchB", color=col))

        self._menu_heads.append(("TEXT  SIZE", rx, card.y + 214))
        for i, (label, scale) in enumerate(TEXT_SIZES):
            self._menu_buttons.append(Button(
                (rx, card.y + 238 + i * 48, rw, 40), label,
                lambda value=scale: self._set_text_scale(value),
                kind="textsize", value=scale))

        self._menu_heads.append(("SOUND", rx, card.y + 390))
        self._menu_buttons.append(Button(
            (rx, card.y + 414, rw, 40),
            "Sound on" if self.sound_enabled else "Sound off",
            self._toggle_sound, kind="toggle", value=self.sound_enabled))

        self._menu_buttons.append(
            Button((cx - 110, card.bottom + 18, 220, 46), "‹  Back",
                   self._close_colors, kind="cta"))
