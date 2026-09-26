"""Deterministically validate every bundled game and guided lesson."""

from chess_game.study import load_game_library, resolve_lesson


def _require_source(source, context):
    if source is None:
        raise ValueError("{} has no source credit".format(context))
    for field in ("name", "license", "attribution"):
        if not getattr(source, field).strip():
            raise ValueError("{} source has no {}".format(context, field))


def main():
    library = load_game_library()
    if library.errors:
        for error in library.errors:
            print("ERROR:", error)
        raise SystemExit(1)
    for entry in library.entries:
        _require_source(entry.game.source, "game " + entry.game.game_id)
        print("game:", entry.game.game_id)
    for entry in library.lesson_entries:
        if not entry.lesson.objective.strip():
            raise ValueError(
                "lesson {} has no objective".format(entry.lesson.lesson_id))
        _require_source(
            entry.lesson.commentary_source,
            "lesson " + entry.lesson.lesson_id)
        resolved = resolve_lesson(entry.game, entry.lesson)
        print("lesson: {} ({} verified steps)".format(
            entry.lesson.lesson_id, len(resolved)))
    for course in library.courses_for_category("opening"):
        _require_source(course.association_source,
                        "course association " + course.course_id)
        _require_source(course.source_game,
                        "course source game " + course.course_id)
        print("course: {} ({} lessons)".format(
            course.course_id, len(course.lesson_ids)))
    print("content pack {!r} is valid".format(library.pack_id))


if __name__ == "__main__":
    main()
