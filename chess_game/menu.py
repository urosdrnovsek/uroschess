"""Menu hierarchy and responsive menu control geometry."""

import pygame

from .views.widgets import Button
from .pieces import WHITE, BLACK
from .difficulty import DIFFICULTIES


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

# Older standalone lessons keep their stable IDs and saved progress. This
# navigation map gives each one a home in the character-led Learn flow.
GUIDE_LESSONS = {
    "pippa-pomeranian": ("opening-essentials", "italian-development",
                           "queens-gambit-plan"),
    "tina-turtle": ("promote-the-pawn", "queen-and-king-mate",
                    "rook-and-king-mate", "square-of-the-pawn",
                    "opposition-and-king-activity"),
    "tom-rabbit": ("black-against-d4",),
    "bruno-bear": ("coordination-before-material",),
}

GUIDE_TOPICS = {
    "chicky": "Piece moves, captures, king safety and checkmate",
    "pippa-pomeranian": "Opening basics and useful developing moves",
    "tina-turtle": "Promotion, active kings and endgame practice",
    "tom-rabbit": "Spot opening threats and choose a reply",
    "bruno-bear": "Make a middlegame plan and coordinate pieces",
    "olive-owl": "Tactics, knight forks and active bishops",
    "monty-cat": "Study a recorded game after beating Monty",
}

GUIDE_SHORT_TOPICS = {
    "chicky": "Moves, captures and checkmate",
    "pippa-pomeranian": "Opening moves and development",
    "tina-turtle": "Promote pawns and finish games",
    "tom-rabbit": "Spot and answer opening threats",
    "bruno-bear": "Plan with bishops and rooks",
    "olive-owl": "Find forks and active squares",
    "monty-cat": "Study a game after beating Monty",
}

GUIDE_PROFILE_TOPICS = {
    "chicky": "Piece moves",
    "pippa-pomeranian": "Opening ideas",
    "tina-turtle": "Pawn endgames",
    "tom-rabbit": "Opening defence",
    "bruno-bear": "Middlegame plans",
    "olive-owl": "Chess tactics",
    "monty-cat": "Recorded game study",
}

class MenuLayoutMixin:
    """Build menu controls while the UI owns their actions and state."""

    def _simple_menu_top(self):
        return max(95, min(218, self.win_h - 436))

    def _study_menu_top(self):
        """Leave room for the card and its navigation at shorter heights."""
        return max(20, min(164, self.win_h - 500))

    def _build_menu_buttons(self):
        self._menu_buttons = []
        self._collection_cards = []
        self._menu_heads = []
        if self.menu_view == "colors":
            self._build_menu_colors()
        elif self.menu_view == "library":
            self._build_menu_library()
        elif self.menu_view == "opening_hub":
            self._build_opening_hub()
        elif self.menu_view == "guided_hub":
            self._build_guided_hub()
        elif self.menu_view == "course":
            self._build_course_menu()
        elif self.menu_view == "course_about":
            self._build_course_about()
        elif self.menu_view == "challenge":
            self._build_challenge_menu()
        elif self.menu_view == "challenge_color":
            self._build_challenge_color_menu()
        elif self.menu_view == "collection":
            self._build_collection_menu()
        elif self.menu_view == "challenge_result":
            self._build_challenge_result_menu()
        elif self.menu_view == "master_award":
            self._build_master_award_menu()
        elif self.menu_view in ("challenge_recovery", "challenge_unavailable",
                                "challenge_archive"):
            self._build_challenge_issue_menu()
        elif self.menu_view == "characters":
            self._build_character_menu()
        elif self.menu_view == "guide_lessons":
            self._build_guide_lessons()
        elif self.menu_view in ("learn", "play", "ai_play"):
            self._build_menu_section()
        else:
            self._build_menu_main()
        if self.menu_view in ("characters", "learn", "guide_lessons"):
            self._feature_rect = pygame.Rect(0, 0, 0, 0)
            return
        card = self._menu_card
        gap = 16
        portrait_height = 140
        if card.top < portrait_height + gap + 8:
            self._feature_rect = pygame.Rect(0, 0, 0, 0)
            return
        portrait_width = min(472, card.w)
        self._feature_rect = pygame.Rect(
            card.centerx - portrait_width // 2,
            card.top - gap - portrait_height,
            portrait_width, portrait_height)

    def _build_menu_main(self):
        card_width = min(472, self.win_w - 24)
        left = (self.win_w - card_width) // 2
        compact = self.win_h < 440
        top = 12 if compact else max(12, min(218, self.win_h - 540))
        card = pygame.Rect(left, top, card_width, 200 if compact else 286)
        self._menu_card = card
        x, w = card.x + 24, card.w - 48
        cx = card.centerx
        for index, (label, action) in enumerate((
                ("Learn", lambda: self._open_menu_section("learn")),
                ("Play", lambda: self._open_menu_section("play")),
                ("Watch games", lambda: self._open_library("replay")),
                ("Meet the characters", lambda: self._open_menu_section(
                    "characters")))):
            self._menu_buttons.append(Button(
                (x, card.y + (9 + index * 47 if compact else
                              18 + index * 64), w, 40 if compact else 54),
                label, action,
                kind="cta" if index == 0 else "step"))
        self._menu_buttons.append(
            Button((cx - min(200, w // 2), card.bottom + (4 if compact else 8),
                    min(400, w), 32 if compact else 42), "Appearance",
                   self._open_colors, kind="cta"))
        self._menu_buttons.append(
            Button((cx - min(200, w // 2), card.bottom + (37 if compact else 50),
                    min(400, w), 28 if compact else 36), "Exit",
                   self._exit, kind="exit"))
        medals_y = card.bottom + (69 if compact else 94)
        self._menu_buttons.append(Button(
            (left + 8, medals_y, card_width - 16, 30 if compact else 42),
            "Medals", self._open_collection, kind="step"))

    def _build_collection_menu(self):
        from .challenge import ROSTER, medal_summary
        width = min(760, self.win_w - 24)
        columns = 2 if self.win_h < 520 or self.win_w >= 560 else 1
        rows = (len(ROSTER) + columns - 1) // columns
        gap = 4 if self.win_h < 420 else 8
        row_height = min(116 if columns == 2 else 82,
                         max(48, (self.win_h - 118 - gap * (rows - 1)) // rows))
        card_height = 50 + rows * row_height + (rows - 1) * gap
        top = max(12, (self.win_h - card_height - 48) // 2)
        card = pygame.Rect((self.win_w - width) // 2, top, width, card_height)
        self._menu_card = card
        x, w = card.x + 12, card.w - 24
        self._menu_heads.append(("MEDALS · LIFETIME WINS", x, top + 13))
        cell_width = (w - gap * (columns - 1)) // columns
        for index, opponent in enumerate(ROSTER):
            count = self.collection_counts[opponent.ident]
            summary = medal_summary(count)
            row, column = divmod(index, columns)
            cell_x = x + column * (cell_width + gap)
            if columns == 2 and index == len(ROSTER) - 1:
                cell_x = card.centerx - cell_width // 2
            self._collection_cards.append(Button(
                (cell_x,
                 top + 42 + row * (row_height + gap),
                 cell_width, row_height),
                opponent.name + " · " + opponent.strength,
                lambda: None, kind="medal_row", detail=summary.label,
                value=opponent.portrait))
        self._menu_buttons.append(Button(
            (x, card.bottom + 8, w, 36), "‹ Back to menu",
            lambda: self._open_menu_section("main"), kind="cta"))

    def _build_challenge_result_menu(self):
        from .challenge import ROSTER

        width = min(472, self.win_w - 24)
        compact = self.win_h < 420
        top = 12 if compact else max(12, min(170, self.win_h - 430))
        card = pygame.Rect((self.win_w - width) // 2, top, width,
                           235 if compact else 292)
        self._menu_card = card
        x, w = card.x + 20, card.w - 40
        self._menu_heads.append(("CHARACTER CHALLENGE RESULT", x, top + 14))
        reward = (self.challenge_progress_snapshot or {}).get("reward")
        award = (self.challenge_progress_snapshot or {}).get("award")
        pending = (award is not None and award["celebration_seen_at"] is None
                   and reward is not None and award["match_id"] ==
                   self.challenge.match_id)
        if pending:
            self._menu_buttons.append(Button(
                (x, top + (160 if compact else 204), w,
                 32 if compact else 38), "Celebrate Uroschess Master",
                self._acknowledge_master, kind="cta"))
        else:
            label = "Play another challenge"
            states = (self.challenge_progress_snapshot or {}).get("states")
            reward = (self.challenge_progress_snapshot or {}).get("reward")
            if states and reward and self.challenge is not None:
                index = ROSTER.index(self.challenge.opponent)
                if states[index] == "black_required":
                    label = "Play {} as Black".format(self.challenge.opponent.name)
                elif states[index] == "complete" and index < len(ROSTER) - 1:
                    label = "Play {} as White".format(ROSTER[index + 1].name)
            self._menu_buttons.append(Button(
                (x, top + (160 if compact else 204), w,
                 32 if compact else 38), label,
                self._next_challenge_from_result, kind="cta"))
        self._menu_buttons.append(Button(
            (x, top + (198 if compact else 249), w,
             32 if compact else 36), "Medals",
            self._open_collection, kind="step"))
        self._menu_buttons.append(Button(
            (x, card.bottom + 7, w, 34 if compact else 38), "‹ All challenges",
            self._open_challenge_from_game, kind="step"))

    def _build_master_award_menu(self):
        width = min(472, self.win_w - 24)
        top = max(12, min(180, self.win_h - 380))
        card = pygame.Rect((self.win_w - width) // 2, top, width, 235)
        self._menu_card = card
        x, w = card.x + 20, card.w - 40
        self._menu_heads.append(("UROSCHESS MASTER", x, top + 16))
        self._menu_buttons.append(Button(
            (x, top + 143, w, 40), "Dismiss celebration",
            self._acknowledge_master, kind="cta"))
        self._menu_buttons.append(Button(
            (x, card.bottom + 8, w, 38), "‹ Back to Play",
            lambda: self._open_menu_section("play"), kind="step"))

    def _build_character_menu(self):
        from .challenge import ROSTER
        width = min(640, self.win_w - 24)
        height = min(580, self.win_h - 95)
        top = max(12, (self.win_h - height - 50) // 2)
        card = pygame.Rect((self.win_w - width) // 2, top, width, height)
        self._menu_card = card
        x, inner = card.x + 20, card.w - 40
        self._menu_heads.append((
            "MEET THE CHARACTERS · {} / {}".format(
                self.character_index + 1, len(ROSTER)), x, top + 14))
        player_id = ROSTER[self.character_index].ident
        available_courses = ([item for item in self.game_library.courses
                              if item.published
                              and item.player_id == player_id]
                             if self.game_library else [])
        course = next((item for item in available_courses
                       if item.category in ("middlegame", "tactics")),
                      available_courses[0] if available_courses else None)
        if course:
            side = (inner - 16) // 3
            unlocked = self._course_unlocked(course)
            self._menu_buttons.extend((
                Button((x, card.bottom - 47, side, 36), "‹ Prev",
                       lambda: self._change_character(-1), kind="step"),
                Button((x + side + 8, card.bottom - 47, side, 36),
                       "Learn" if unlocked else "Locked",
                       lambda: self._open_course(course.course_id),
                       kind="cta"),
                Button((x + 2 * (side + 8), card.bottom - 47,
                        inner - 2 * (side + 8), 36), "Next ›",
                       lambda: self._change_character(1), kind="step")))
        else:
            half = (inner - 8) // 2
            self._menu_buttons.extend((
                Button((x, card.bottom - 47, half, 36), "‹ Previous",
                       lambda: self._change_character(-1), kind="step"),
                Button((x + half + 8, card.bottom - 47, inner - half - 8, 36),
                       "Next ›", lambda: self._change_character(1),
                       kind="step")))
        self._menu_buttons.append(Button(
            (x, card.bottom + 8, inner, 38), "‹ Back to menu",
            lambda: self._open_menu_section("main"), kind="cta"))

    def _open_menu_section(self, section):
        self._reset_button_focus()
        self.menu_view = section
        self._menu_buttons = []
        self._change_chess_thought(play_sound=False)

    def _guide_entries(self, player_id):
        if not self.game_library:
            return ()
        courses = tuple(course for course in self.game_library.courses
                        if course.published and course.player_id == player_id)
        lessons = tuple(self.game_library.lesson_entry(lesson_id)
                        for lesson_id in GUIDE_LESSONS.get(player_id, ()))
        return courses + tuple(entry for entry in lessons if entry is not None)

    def _build_learn_guides(self):
        from .challenge import ROSTER
        width = min(660, self.win_w - 24)
        height = min(430, self.win_h - 70)
        top = max(12, min(164, self.win_h - height - 48))
        card = pygame.Rect((self.win_w - width) // 2, top, width, height)
        self._menu_card = card
        x, inner = card.x + 16, card.w - 32
        per_page = 4 if height >= 380 else 2
        page_count = (len(ROSTER) + per_page - 1) // per_page
        self.guide_page = max(0, min(self.guide_page, page_count - 1))
        heading = ("CHOOSE A GUIDE" if width < 440 else
                   "CHOOSE YOUR CHESS GUIDE")
        self._menu_heads.append((
            "{} · {}/{}".format(heading, self.guide_page + 1, page_count),
            x, top + 13))
        gap = 7
        row_height = (height - 53 - gap * (per_page - 1)) // per_page
        for index, opponent in enumerate(ROSTER[
                self.guide_page * per_page:(self.guide_page + 1) * per_page]):
            self._menu_buttons.append(Button(
                (x, top + 39 + index * (row_height + gap), inner, row_height),
                opponent.name,
                lambda ident=opponent.ident: self._open_guide_lessons(ident),
                kind="guide", detail=(GUIDE_SHORT_TOPICS[opponent.ident]
                                      if width < 440 and self.text_scale > 1.0
                                      else GUIDE_TOPICS[opponent.ident]),
                value=opponent.ident))
        self._build_guide_navigation(x, inner, card.bottom + 7,
                                     self.guide_page, page_count,
                                     self._change_guide_page,
                                     lambda: self._open_menu_section("main"))

    def _build_guide_lessons(self):
        from .challenge import OPPONENTS
        opponent = OPPONENTS.get(self.active_guide_id)
        if opponent is None:
            self._build_learn_guides()
            return
        width = min(660, self.win_w - 24)
        height = min(430, self.win_h - 70)
        top = max(12, min(164, self.win_h - height - 48))
        card = pygame.Rect((self.win_w - width) // 2, top, width, height)
        self._menu_card = card
        x, inner = card.x + 16, card.w - 32
        compact = height < 320
        profile_height = 72 if compact else 96
        self._guide_profile_rect = pygame.Rect(x, top + 11, inner,
                                               profile_height)
        entries = self._guide_entries(opponent.ident)
        per_page = 2 if compact else 3
        page_count = max(1, (len(entries) + per_page - 1) // per_page)
        self.guide_lesson_page = max(0, min(self.guide_lesson_page,
                                            page_count - 1))
        start = self.guide_lesson_page * per_page
        visible = entries[start:start + per_page]
        gap = 7
        row_top = self._guide_profile_rect.bottom + 10
        row_height = (card.bottom - 10 - row_top - gap * (per_page - 1)) // per_page
        for index, entry in enumerate(visible):
            if hasattr(entry, "course_id"):
                unlocked = self._course_unlocked(entry)
                label = entry.title if unlocked else "Monty's recorded game"
                detail = ("Locked · beat Monty once in Character Challenge"
                          if not unlocked else entry.description)
                action = lambda ident=entry.course_id: self._open_course(ident)
            else:
                label = entry.lesson.title
                detail = "{} min · {}".format(
                    entry.lesson.estimated_minutes,
                    self._guide_lesson_status(entry))
                action = lambda item=entry: self.start_lesson(item)
            self._menu_buttons.append(Button(
                (x, row_top + index * (row_height + gap), inner, row_height),
                label, action, kind="library", detail=detail))
        self._build_guide_navigation(x, inner, card.bottom + 7,
                                     self.guide_lesson_page, page_count,
                                     self._change_guide_lesson_page,
                                     lambda: self._open_menu_section("learn"))

    def _build_guide_navigation(self, x, width, y, page, page_count,
                                change_page, back):
        gap = 7
        side = (width - 2 * gap) // 3
        center = width - 2 * side - 2 * gap
        if page > 0:
            self._menu_buttons.append(Button(
                (x, y, side, 36), "‹ Prev", lambda: change_page(-1),
                kind="step"))
        self._menu_buttons.append(Button(
            (x + side + gap, y, center, 36), "Back", back, kind="cta"))
        if page < page_count - 1:
            self._menu_buttons.append(Button(
                (x + side + center + 2 * gap, y, side, 36), "Next ›",
                lambda: change_page(1), kind="step"))

    def _guide_lesson_status(self, entry):
        if self.progress_store is None:
            return "Practice lesson"
        try:
            record = self.progress_store.load(
                entry.lesson.lesson_id, entry.lesson.content_revision)
        except Exception as error:
            self.progress_error = str(error)
            return "Practice lesson"
        if record is None:
            return "Practice lesson"
        return "Done" if record.completed else "In progress"

    def _build_menu_section(self):
        if self.menu_view == "learn":
            self._build_learn_guides()
            return
        width = min(472, self.win_w - 24)
        top = self._simple_menu_top()
        card = pygame.Rect((self.win_w - width) // 2, top, width, 390)
        self._menu_card = card
        x, w = card.x + 24, card.w - 48
        gap, half = 8, (w - 8) // 2
        if self.menu_view == "play":
            self._menu_heads.append(("PLAY CHESS", x, top + 16))
            self._menu_buttons.append(Button(
                (x, top + 45, w, 48), "Play against AI",
                lambda: self._open_menu_section("ai_play"), kind="cta"))
            self._menu_buttons.append(Button(
                (x, top + 103, w, 48), "Two players",
                lambda: self.start_game({WHITE, BLACK}), kind="step"))
            self._menu_buttons.append(Button(
                (x, top + 161, w, 48), "Character Challenge",
                self._open_challenge_menu, kind="step"))
            self._menu_buttons.append(Button(
                    (x, top + 219, w, 48), "Saved match archive",
                    self._open_challenge_archive, kind="step"))
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

    def _build_challenge_menu(self):
        from .challenge import ROSTER
        width = min(500, self.win_w - 24)
        top = max(18, min(164, self.win_h - 574))
        card = pygame.Rect((self.win_w - width) // 2, top, width, 490)
        self._menu_card = card
        x, w = card.x + 20, card.w - 40
        snapshot = self.challenge_snapshot
        heading = ("UROSCHESS MASTER · CHARACTER CHALLENGE"
                   if snapshot["master"] else "CHARACTER CHALLENGE")
        self._menu_heads.append((heading, x, top + 13))
        states = snapshot["states"]
        victories = snapshot["victories"]
        saved = snapshot["saved"]
        next_index = next((index for index, state in enumerate(states)
                           if state in ("white_required", "black_required")),
                          None)
        if next_index is None:
            goal = "Uroschess Master earned"
        else:
            color = ("White" if states[next_index] == "white_required"
                     else "Black")
            goal = "Next: {} as {}".format(ROSTER[next_index].name, color)
        self._menu_heads.extend((
            ("{}/14 colour badges".format(len(victories)), x, top + 34),
            (goal, x, top + 54)))
        page_count = (len(ROSTER) + 3) // 4
        self.challenge_page = max(0, min(self.challenge_page, page_count - 1))
        first = self.challenge_page * 4
        for row, opponent in enumerate(ROSTER[first:first + 4]):
            index = first + row
            state = states[index]
            detail = {
                "locked": "Beat {} with both colours".format(
                    ROSTER[index - 1].name) if index else "Locked",
                "white_required": "Win with White",
                "black_required": "White won · play Black",
                "complete": "White ✓  Black ✓ · complete",
            }[state]
            label = "{} · {}".format(opponent.name, opponent.strength)
            action = (lambda ident=opponent.ident:
                      self._choose_challenge_opponent(ident)) if (
                          state != "locked" and not saved) else None
            self._menu_buttons.append(Button(
                (x, top + 76 + row * 80, w, 80), label,
                action or (lambda: None), kind="challenge", detail=detail,
                value=opponent.portrait))
        half = (w - 8) // 2
        if self.challenge_page > 0:
            self._menu_buttons.append(Button(
                (x, top + 410, half, 36),
                "‹ Prev" if self.win_w < 420 else "‹ Previous characters",
                lambda: self._change_challenge_page(-1), kind="step"))
        if self.challenge_page < page_count - 1:
            self._menu_buttons.append(Button(
                (x + half + 8, top + 410, w - half - 8, 36),
                "Next ›" if self.win_w < 420 else "Next characters ›",
                lambda: self._change_challenge_page(1),
                kind="step"))
        if saved:
            self._menu_buttons.append(Button(
                (x, card.bottom + 6, (w - 8) // 2, 36), "Resume",
                self._resume_challenge, kind="cta"))
            self._menu_buttons.append(Button(
                (x + (w + 8) // 2, card.bottom + 6, (w - 8) // 2, 36),
                "Discard", self._discard_challenge, kind="step"))
        self._menu_buttons.append(Button(
            (x, card.bottom + 48, w, 36), "‹  Back to Play",
            lambda: self._open_menu_section("play"), kind="cta"))

    def _build_challenge_color_menu(self):
        from .challenge import OPPONENTS, ROSTER
        opponent = OPPONENTS[self.challenge_choice_id]
        state = self.challenge_snapshot["states"][ROSTER.index(opponent)]
        width = min(472, self.win_w - 24)
        top = self._simple_menu_top()
        card = pygame.Rect((self.win_w - width) // 2, top, width, 260)
        self._menu_card = card
        x, w = card.x + 24, card.w - 48
        self._menu_heads.append((opponent.name.upper() + " · " +
                                 opponent.strength.upper(), x, top + 16))
        self._menu_buttons.append(Button(
            (x, top + 53, w, 48), "Play as White",
            lambda ident=opponent.ident: self._start_challenge(WHITE, ident),
            kind="cta"))
        if state in ("black_required", "complete"):
            self._menu_buttons.append(Button(
                (x, top + 113, w, 48), "Play as Black",
                lambda ident=opponent.ident: self._start_challenge(BLACK, ident),
                kind="step"))
        self._menu_buttons.append(Button(
            (x, card.bottom + 8, w, 38), "‹  All characters",
            self._open_challenge_menu, kind="step"))

    def _build_challenge_issue_menu(self):
        width = min(500, self.win_w - 24)
        top = max(18, min(164, self.win_h - 450))
        card = pygame.Rect((self.win_w - width) // 2, top, width, 332)
        self._menu_card = card
        x, w = card.x + 20, card.w - 40
        recovery = self.menu_view == "challenge_recovery"
        archive = self.menu_view == "challenge_archive"
        if recovery:
            heading = "SAVED MATCH NEEDS ATTENTION"
        elif archive and self.archive_entries:
            heading = "ARCHIVED MATCH {} / {}".format(
                self.archive_index + 1, len(self.archive_entries))
        elif archive:
            heading = "SAVED MATCH ARCHIVE"
        else:
            heading = "CHALLENGE PROGRESS UNAVAILABLE"
        self._menu_heads.append((heading, x, top + 15))
        if recovery:
            actions = (
                ("Retry saved match", self._resume_challenge),
                ("Export saved match", self._export_challenge_recovery),
                ("Archive and start again", self._archive_challenge_recovery),
                ("Back to Play", lambda: self._open_menu_section("play")),
            )
        elif archive:
            actions = []
            if self.archive_entries:
                actions.append(("Export saved match", self._export_challenge_recovery))
                if self.archive_index > 0:
                    actions.append(("Previous archive",
                                    lambda: self._change_challenge_archive(-1)))
                if self.archive_index + 1 < len(self.archive_entries):
                    actions.append(("Next archive",
                                    lambda: self._change_challenge_archive(1)))
            actions.append(("Back to Play", lambda: self._open_menu_section("play")))
        else:
            actions = (
                ("Retry", self._open_challenge_menu),
                ("Back to Play", lambda: self._open_menu_section("play")),
            )
        for index, (label, action) in enumerate(actions):
            self._menu_buttons.append(Button(
                (x, top + 122 + index * 48, w, 40), label, action,
                kind="cta" if index == 0 else "step"))

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

    def _build_guided_hub(self):
        width = min(660, self.win_w - 24)
        top = self._study_menu_top()
        card = pygame.Rect((self.win_w - width) // 2, top, width, 420)
        self._menu_card = card
        x, inner = card.x + 22, card.w - 44
        self._menu_heads.append(("GUIDED GAMES AND PLANS", x, top + 16))
        courses = self._guided_courses()
        page_count = max(1, (len(courses) + 1) // 2)
        self.guided_course_page = max(0, min(self.guided_course_page,
                                             page_count - 1))
        visible = courses[self.guided_course_page * 2:
                          (self.guided_course_page + 1) * 2]
        for index, course in enumerate(visible):
            unlocked = self._course_unlocked(course)
            self._menu_buttons.append(Button(
                (x, top + 55 + index * 119, inner, 106),
                course.title if unlocked else "Monty's game",
                lambda ident=course.course_id: self._open_course(ident),
                kind="player" if unlocked else "library",
                detail=("Locked: beat Monty once\neither colour"
                        if not unlocked else ""),
                value=course.course_id))
        self._menu_buttons.append(
            Button((x, top + 300, inner, 55), "All guided games",
                   lambda: self._open_library("guided_game"), kind="step"))
        if page_count > 1:
            gap = 8
            side = (inner - 2 * gap) // 3
            center = inner - 2 * side - 2 * gap
            self._menu_buttons.extend((
                Button((x, card.bottom + 8, side, 38), "‹ Prev",
                       lambda: self._change_guided_course_page(-1), kind="step"),
                Button((x + side + gap, card.bottom + 8, center, 38), "Back",
                       lambda: self._open_menu_section("learn"), kind="cta"),
                Button((x + side + center + 2 * gap, card.bottom + 8,
                        side, 38), "Next ›",
                       lambda: self._change_guided_course_page(1), kind="step")))
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
        heading = ((course.opening_name + " WITH ") if course.opening_name
                   else "LEARN WITH ")
        self._menu_heads.append((heading.upper() +
                                 self.game_library.player(course.player_id).short_name.upper(),
                                 x, top + 16))
        self._course_profile_rect = pygame.Rect(x, top + 42, inner, 100)
        entries = self.game_library.course_lessons(course)
        missing_basics = self._course_missing_prerequisites(course)
        complete = bool(entries) and all(
            self._course_entry_status(entry, course) in ("DONE", "REVISIT")
            for entry in entries)
        self._menu_heads.append(("PRACTISE BASICS FIRST · OR TRY A LESSON"
                                 if missing_basics else
                                 "COURSE COMPLETE · PRACTISE AGAIN"
                                 if complete else "LESSONS WITH " +
                                 self.game_library.player(course.player_id).short_name.upper(),
                                 x, top + 151))
        page_size = 2 if len(entries) > 3 else 3
        page_count = max(1, (len(entries) + page_size - 1) // page_size)
        self.course_lesson_page = max(0, min(self.course_lesson_page,
                                             page_count - 1))
        visible = entries[self.course_lesson_page * page_size:
                          (self.course_lesson_page + 1) * page_size]
        for index, entry in enumerate(visible):
            status = self._course_entry_status(entry, course)
            detail = ("LATER · Try earlier lesson first" if status == "LATER"
                      else "{}  ·  {} min  ·  {}".format(
                          status, entry.lesson.estimated_minutes,
                          "Recorded game" if course.content_kind ==
                          "historical_analysis" else "Practice position"))
            self._menu_buttons.append(Button(
                (x, top + 175 + index * 70, inner, 62),
                entry.lesson.title,
                lambda item=entry: self.start_lesson(
                    item, course_id=course.course_id),
                kind="library", detail=detail))
        if page_count > 1:
            half = (inner - 8) // 2
            compact = inner < 380 or self.text_scale >= 1.2
            if self.course_lesson_page > 0:
                self._menu_buttons.append(Button(
                    (x, top + 319, half, 36),
                    "‹ Prev" if compact else "‹ Previous lessons",
                    lambda: self._change_course_lesson_page(-1), kind="step"))
            if self.course_lesson_page < page_count - 1:
                self._menu_buttons.append(Button(
                    (x + half + 8, top + 319, inner - half - 8, 36),
                    "Next ›" if compact else "More lessons ›",
                    lambda: self._change_course_lesson_page(1), kind="step"))
        started = any(self._course_entry_status(entry, course) in
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
            lambda: self._open_menu_section(self.course_return_view), kind="cta"))
        if course.source_game_id and course.association_source:
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
            ("GAME BACKGROUND" if course.content_kind == "historical_analysis"
             else "OPENING BACKGROUND", x, top + 116),
            ("ARCHIVAL GAME", x, top + 172),
            ("PORTRAIT CREDIT", x, top + 237),
        ))
        self._course_about_rect = pygame.Rect(x, top + 35, inner, 225)
        self._menu_buttons.extend((
            Button((x, top + 297, inner, 36),
                   "Read game source" if course.content_kind == "historical_analysis"
                   else "Read opening source",
                   lambda: self._open_source_link(course.association_source.url),
                   kind="step"),
            Button((x, top + 343, inner, 36), "Watch a game",
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
        top = max(20, min(164, self.win_h - 542))
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
