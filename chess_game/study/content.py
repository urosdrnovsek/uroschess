"""Load and validate packaged teaching content without network access."""

from dataclasses import dataclass, replace
from importlib import resources
import json

from .models import (
    BoardArrow,
    GameRecord,
    Lesson,
    LessonQuestion,
    LessonStep,
    MoveAnswer,
    ReviewedMove,
    SourceInfo,
    SquareHighlight,
)
from .pgn_service import PgnParseError, parse_pgn_games


class ContentLoadError(ValueError):
    """A content manifest or one of its resources is invalid."""


@dataclass(frozen=True)
class LibraryEntry:
    game: GameRecord
    title: str
    level: str
    themes: tuple
    description: str
    lesson: object = None
    category: str = "guided_game"


@dataclass(frozen=True)
class PlayerProfile:
    player_id: str
    name: str
    short_name: str
    portrait: str
    intro: str
    biography_source: SourceInfo = None
    portrait_attribution: str = ""


@dataclass(frozen=True)
class OpeningCourse:
    course_id: str
    player_id: str
    title: str
    opening_name: str
    description: str
    lesson_ids: tuple
    association_source: SourceInfo
    level: str = "beginner"
    prerequisite_lesson_ids: tuple = ()
    published: bool = True
    source_game: SourceInfo = None
    source_game_id: str = ""
    card_title: str = ""


@dataclass(frozen=True)
class GameLibrary:
    pack_id: str
    title: str
    entries: tuple
    errors: tuple = ()
    lessons: tuple = ()
    lesson_entries: tuple = ()
    players: tuple = ()
    courses: tuple = ()
    learning_path: tuple = ()

    @property
    def games_by_id(self):
        return {entry.game.game_id: entry.game for entry in self.entries}

    @property
    def lessons_by_id(self):
        return {entry.lesson.lesson_id: entry for entry in self.lesson_entries}

    @property
    def players_by_id(self):
        return {player.player_id: player for player in self.players}

    @property
    def courses_by_id(self):
        return {course.course_id: course for course in self.courses}

    def courses_for_category(self, category):
        if category != "opening":
            return ()
        return tuple(course for course in self.courses if course.published)

    def lesson_entry(self, lesson_id):
        return next((entry for entry in self.lesson_entries
                     if entry.lesson.lesson_id == lesson_id), None)

    def player(self, player_id):
        return next((player for player in self.players
                     if player.player_id == player_id), None)

    def course(self, course_id):
        return next((course for course in self.courses
                     if course.course_id == course_id), None)

    def course_lessons(self, course):
        return tuple(self.lesson_entry(lesson_id)
                     for lesson_id in course.lesson_ids)


def _string_tuple(value, field_name):
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ContentLoadError("{} must be a list".format(field_name))
    return tuple(str(item) for item in value)


def _source_info(value, field_name):
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ContentLoadError("{} must be an object".format(field_name))
    return SourceInfo(
        name=str(value.get("name", "")).strip(),
        url=str(value.get("url", "")),
        license=str(value.get("license", "")),
        attribution=str(value.get("attribution", "")),
    )


def _parse_question(value, context):
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ContentLoadError("{} question must be an object".format(context))
    evaluator = str(value.get("evaluator", "reviewed_moves"))
    answers_data = value.get("answers", [])
    if not isinstance(answers_data, list):
        raise ContentLoadError("{} question answers must be a list".format(context))
    answers = []
    for index, answer in enumerate(answers_data):
        if not isinstance(answer, dict):
            raise ContentLoadError(
                "{} answer {} must be an object".format(context, index))
        answers.append(MoveAnswer(
            uci=str(answer.get("uci", "")),
            outcome=str(answer.get("outcome", "")),
            feedback=str(answer.get("feedback", "")),
            reply_moves=_string_tuple(
                answer.get("reply_moves"), "{} reply_moves".format(context)),
        ))

    def parse_tree_node(item, path):
        if not isinstance(item, dict):
            raise ContentLoadError("{} {} must be an object".format(context, path))
        children_data = item.get("children", [])
        if not isinstance(children_data, list):
            raise ContentLoadError("{} {} children must be a list".format(
                context, path))
        children = tuple(parse_tree_node(child, "{}.children[{}]".format(
            path, index)) for index, child in enumerate(children_data))
        try:
            return ReviewedMove(
                uci=str(item.get("uci", "")),
                role=str(item.get("role", "")),
                outcome=str(item.get("outcome", "")),
                feedback=str(item.get("feedback", "")),
                children=children,
                next_prompt=str(item.get("next_prompt", "")),
                hints=_string_tuple(item.get("hints"), "{} hints".format(path)),
            )
        except ValueError as error:
            raise ContentLoadError(
                "{} {}: {}".format(context, path, error)) from error

    tree_data = value.get("tree", [])
    if not isinstance(tree_data, list):
        raise ContentLoadError("{} question tree must be a list".format(context))
    tree = tuple(parse_tree_node(item, "tree[{}]".format(index))
                 for index, item in enumerate(tree_data))
    return LessonQuestion(
        prompt=str(value.get("prompt", "")),
        answers=tuple(answers),
        hints=_string_tuple(value.get("hints"), "{} hints".format(context)),
        kind=str(value.get("kind", "move")),
        timing=str(value.get("timing", "before_move")),
        evaluator=evaluator,
        other_legal_move_text=str(value.get(
            "other_legal_move_text",
            "That move is legal, but it is not covered by this exercise. "
            "Explore it, then return to the lesson.")),
        tree=tree,
    )


def parse_lesson_data(value, source_name="lesson data"):
    """Parse one in-memory lesson document using the packaged-data contract."""
    if not isinstance(value, dict):
        raise ContentLoadError("{} must contain a JSON object".format(source_name))
    steps_data = value.get("steps")
    if not isinstance(steps_data, list):
        raise ContentLoadError("{} steps must be a list".format(source_name))
    steps = []
    for index, item in enumerate(steps_data):
        if not isinstance(item, dict):
            raise ContentLoadError("{} step {} must be an object".format(
                source_name, index))
        context = "{} step {!r}".format(source_name, item.get("step_id", index))
        arrows_data = item.get("arrows", [])
        highlights_data = item.get("highlights", [])
        if not isinstance(arrows_data, list) or not isinstance(highlights_data, list):
            raise ContentLoadError(
                "{} arrows and highlights must be lists".format(context))
        arrows = tuple(BoardArrow(
            from_square=str(arrow.get("from", "")),
            to_square=str(arrow.get("to", "")),
            role=str(arrow.get("role", "idea")),
        ) for arrow in arrows_data if isinstance(arrow, dict))
        if len(arrows) != len(arrows_data):
            raise ContentLoadError("{} arrow must be an object".format(context))
        highlights = tuple(SquareHighlight(
            square=str(highlight.get("square", "")),
            role=str(highlight.get("role", "focus")),
        ) for highlight in highlights_data if isinstance(highlight, dict))
        if len(highlights) != len(highlights_data):
            raise ContentLoadError("{} highlight must be an object".format(context))
        steps.append(LessonStep(
            step_id=str(item.get("step_id", "")),
            node_path=_string_tuple(
                item.get("node_path"), "{} node_path".format(context)),
            expected_fen=str(item.get("expected_fen", "")),
            explanation=str(item.get("explanation", "")),
            detail=str(item.get("detail", "")),
            arrows=arrows,
            highlights=highlights,
            question=_parse_question(item.get("question"), context),
            coach_prompt=str(item.get("coach_prompt", "")),
            practice_mode=str(item.get("practice_mode", "guided")),
        ))
    try:
        revision = int(value.get("content_revision", 0))
        minutes = int(value.get("estimated_minutes", 0))
        schema_version = int(value.get("schema_version", 0))
    except (TypeError, ValueError) as error:
        raise ContentLoadError(
            "{} has invalid numeric metadata".format(source_name)) from error
    return Lesson(
        lesson_id=str(value.get("lesson_id", "")),
        content_revision=revision,
        title=str(value.get("title", "")),
        level=str(value.get("level", "")),
        estimated_minutes=minutes,
        objective=str(value.get("objective", "")),
        game_id=str(value.get("game_id", "")),
        steps=tuple(steps),
        concepts=_string_tuple(value.get("concepts"), "concepts"),
        takeaway=str(value.get("takeaway", "")),
        schema_version=schema_version,
        prerequisites=_string_tuple(value.get("prerequisites"), "prerequisites"),
        commentary_source=_source_info(
            value.get("commentary_source"), "commentary_source"),
        coach_player_id=str(value.get("coach_player_id", "")),
        content_kind=str(value.get("content_kind", "synthetic")),
        related_source_game_id=str(value.get("related_source_game_id", "")),
        initial_help=bool(value.get("initial_help", False)),
    )


def _read_text(package, name):
    try:
        files = getattr(resources, "files", None)
        if files is not None:
            return files(package).joinpath(name).read_text(encoding="utf-8")
        return resources.read_text(package, name, encoding="utf-8")
    except (OSError, FileNotFoundError, ModuleNotFoundError) as error:
        raise ContentLoadError(
            "cannot read {} from {}: {}".format(name, package, error)) from error


def load_game_library(pack_package="chess_game.content.starter"):
    """Load a packaged game library, retaining errors for individual entries."""
    try:
        manifest = json.loads(_read_text(pack_package, "manifest.json"))
    except (json.JSONDecodeError, ContentLoadError) as error:
        raise ContentLoadError("invalid content manifest: " + str(error)) from error

    if not isinstance(manifest, dict):
        raise ContentLoadError("content manifest must be a JSON object")
    if manifest.get("schema_version") != 1:
        raise ContentLoadError("unsupported content manifest schema")
    pack_id = manifest.get("pack_id", "").strip()
    if not pack_id:
        raise ContentLoadError("content manifest requires pack_id")

    entries = []
    errors = []
    game_package = pack_package + ".games"
    seen_ids = set()
    games = manifest.get("games", [])
    if not isinstance(games, list):
        raise ContentLoadError("content manifest games must be a list")
    for item in games:
        if not isinstance(item, dict):
            errors.append("invalid game entry: expected an object")
            continue
        game_id = str(item.get("game_id", "")).strip()
        filename = str(item.get("file", "")).strip()
        if (not game_id or game_id in seen_ids or not filename
                or "/" in filename or "\\" in filename):
            errors.append("invalid or duplicate game entry: {!r}".format(game_id))
            continue
        seen_ids.add(game_id)
        source_data = item.get("source") or {}
        if not isinstance(source_data, dict):
            errors.append("{}: source must be an object".format(game_id))
            continue
        source = SourceInfo(
            name=str(source_data.get("name", "Bundled content")),
            url=str(source_data.get("url", "")),
            license=str(source_data.get("license", "")),
            attribution=str(source_data.get("attribution", "")),
        )
        category = str(item.get("category", "guided_game"))
        if category not in ("guided_game", "opening", "endgame", "source_game"):
            errors.append("{}: unsupported category {!r}".format(
                game_id, category))
            continue
        try:
            text = _read_text(game_package, filename)
            games = parse_pgn_games(
                text, source="{}:{}".format(pack_id, filename),
                source_info=source)
            if len(games) != 1:
                raise ContentLoadError(
                    "{} must contain exactly one game".format(filename))
            game = replace(games[0], game_id=game_id, source=source)
            entries.append(LibraryEntry(
                game=game,
                title=str(item.get("title") or game.headers.get("Event") or game_id),
                level=str(item.get("level", "intermediate")),
                themes=tuple(str(value) for value in item.get("themes", [])),
                description=str(item.get("description", "")),
                category=category,
            ))
        except (ContentLoadError, PgnParseError, ValueError) as error:
            errors.append("{}: {}".format(game_id, error))

    lessons = []
    lesson_entries = []
    lesson_package = pack_package + ".lessons"
    lesson_items = manifest.get("lessons", [])
    if not isinstance(lesson_items, list):
        raise ContentLoadError("content manifest lessons must be a list")
    entry_by_game = {entry.game.game_id: entry for entry in entries}
    seen_lesson_ids = set()
    for item in lesson_items:
        if not isinstance(item, dict):
            errors.append("invalid lesson entry: expected an object")
            continue
        lesson_id = str(item.get("lesson_id", "")).strip()
        game_id = str(item.get("game_id", "")).strip()
        filename = str(item.get("file", "")).strip()
        if (not lesson_id or lesson_id in seen_lesson_ids or not game_id
                or not filename or "/" in filename or "\\" in filename):
            errors.append("invalid or duplicate lesson entry: {!r}".format(lesson_id))
            continue
        seen_lesson_ids.add(lesson_id)
        try:
            lesson_data = json.loads(_read_text(lesson_package, filename))
            lesson = parse_lesson_data(lesson_data, filename)
            if lesson.lesson_id != lesson_id or lesson.game_id != game_id:
                raise ContentLoadError(
                    "manifest identity does not match lesson file")
            entry = entry_by_game.get(game_id)
            if entry is None:
                raise ContentLoadError("source game {!r} is unavailable".format(game_id))
            from .lessons import resolve_lesson
            resolve_lesson(entry.game, lesson)
            lessons.append(lesson)
            replacement = replace(entry, lesson=lesson)
            lesson_entries.append(replacement)
            if entry.lesson is None:
                entries[entries.index(entry)] = replacement
                entry_by_game[game_id] = replacement
        except (ContentLoadError, json.JSONDecodeError, ValueError) as error:
            errors.append("{}: {}".format(lesson_id, error))

    players, courses = _load_player_courses(
        pack_package, tuple(lesson_entries), tuple(entries), errors)
    learning_path = _string_tuple(
        manifest.get("learning_path"), "learning_path")
    known_lessons = {entry.lesson.lesson_id for entry in lesson_entries}
    if len(learning_path) != len(set(learning_path)) or any(
            lesson_id not in known_lessons for lesson_id in learning_path):
        errors.append("learning_path has duplicate or unknown lessons")
    return GameLibrary(
        pack_id=pack_id,
        title=str(manifest.get("title", pack_id)),
        entries=tuple(entries),
        lessons=tuple(lessons),
        lesson_entries=tuple(lesson_entries),
        players=players,
        courses=courses,
        learning_path=learning_path,
        errors=tuple(errors),
    )


def _load_player_courses(pack_package, lesson_entries, game_entries, errors):
    """Load optional player courses after every lesson has been indexed."""
    has_players = resources.is_resource(pack_package, "players.json")
    has_courses = resources.is_resource(pack_package, "courses.json")
    if not has_players and not has_courses:
        return (), ()
    if not has_players or not has_courses:
        errors.append("player courses require both players.json and courses.json")
        return (), ()
    try:
        player_data = json.loads(_read_text(pack_package, "players.json"))
        course_data = json.loads(_read_text(pack_package, "courses.json"))
    except ContentLoadError as error:
        errors.append("invalid player course data: " + str(error))
        return (), ()
    except json.JSONDecodeError as error:
        errors.append("invalid player course data: " + str(error))
        return (), ()
    if (not isinstance(player_data, dict) or
            player_data.get("schema_version") != 1 or
            not isinstance(player_data.get("players"), list) or
            not isinstance(course_data, dict) or
            course_data.get("schema_version") != 1 or
            not isinstance(course_data.get("courses"), list)):
        errors.append("invalid player course schema")
        return (), ()

    players = []
    for item in player_data["players"]:
        try:
            player = PlayerProfile(
                player_id=str(item["player_id"]), name=str(item["name"]),
                short_name=str(item["short_name"]),
                portrait=str(item["portrait"]), intro=str(item["intro"]),
                biography_source=_source_info(
                    item.get("biography_source"), "biography_source"),
                portrait_attribution=str(item.get("portrait_attribution", "")))
            if (not all((player.player_id, player.name, player.short_name,
                         player.intro, player.portrait,
                         player.portrait_attribution)) or
                    "/" in player.portrait or "\\" in player.portrait or
                    not player.portrait.endswith(".bmp") or
                    not resources.is_resource(
                        "chess_game.assets.portraits", player.portrait) or
                    any(old.player_id == player.player_id for old in players)):
                raise ValueError("invalid identity or portrait")
            players.append(player)
        except (KeyError, TypeError, ValueError) as error:
            errors.append("invalid player profile: " + str(error))

    by_lesson = {entry.lesson.lesson_id: entry for entry in lesson_entries}
    by_game = {entry.game.game_id: entry for entry in game_entries}
    for entry in lesson_entries:
        coach_id = entry.lesson.coach_player_id
        if coach_id and not any(player.player_id == coach_id
                                for player in players):
            errors.append("lesson {} has unknown coach {}".format(
                entry.lesson.lesson_id, coach_id))
    courses = []
    for item in course_data["courses"]:
        try:
            lesson_ids = tuple(str(value) for value in item["lesson_ids"])
            source = _source_info(item["association_source"],
                                  "association_source")
            course = OpeningCourse(
                course_id=str(item["course_id"]),
                player_id=str(item["player_id"]),
                title=str(item["title"]),
                opening_name=str(item["opening_name"]),
                description=str(item["description"]),
                lesson_ids=lesson_ids, association_source=source,
                level=str(item.get("level", "beginner")),
                prerequisite_lesson_ids=_string_tuple(
                    item.get("prerequisite_lesson_ids"),
                    "prerequisite_lesson_ids"),
                published=bool(item.get("published", True)),
                source_game=_source_info(item.get("source_game"),
                                         "source_game"),
                source_game_id=str(item.get("source_game_id", "")),
                card_title=str(item.get("card_title", "")))
            if (not course.course_id or not course.title or
                    not course.opening_name or not course.description or
                    not lesson_ids or
                    len(lesson_ids) != len(set(lesson_ids)) or
                    any(old.course_id == course.course_id for old in courses) or
                    not any(player.player_id == course.player_id
                            for player in players) or
                    any(lesson_id not in by_lesson or
                        by_lesson[lesson_id].lesson.coach_player_id !=
                        course.player_id or
                        by_lesson[lesson_id].lesson.related_source_game_id !=
                        course.source_game_id for lesson_id in lesson_ids) or
                    not source or not all((source.name, source.url,
                                           source.license, source.attribution)) or
                    course.level not in ("beginner", "intermediate") or
                    any(lesson_id not in by_lesson for lesson_id in
                        course.prerequisite_lesson_ids)):
                raise ValueError("missing player, lesson, or association source")
            if course.published:
                if (len(lesson_ids) != 3 or not course.source_game or
                        not course.source_game_id or
                        course.source_game_id not in by_game or
                        by_game[course.source_game_id].category != "source_game" or
                        not all((course.source_game.name,
                                 course.source_game.license,
                                 course.source_game.attribution)) or
                        by_lesson[lesson_ids[-1]].lesson.steps[-1].practice_mode
                        != "independent"):
                    raise ValueError("published course needs three lessons, a "
                                     "source game, and a final independent try")
            courses.append(course)
        except (KeyError, TypeError, ValueError, ContentLoadError) as error:
            errors.append("invalid opening course: " + str(error))
    return tuple(players), tuple(courses)
