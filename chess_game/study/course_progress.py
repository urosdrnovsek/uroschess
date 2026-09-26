"""Course status derived from revisioned lesson and step records."""

from dataclasses import dataclass


@dataclass(frozen=True)
class CourseSummary:
    statuses: dict
    done_count: int
    missing_prerequisites: tuple

    def status(self, lesson_id):
        return self.statuses.get(lesson_id, "NEXT")


def build_course_summary(library, course, store):
    """Read each relevant record once; a missing store leaves lessons playable."""
    missing = []
    for lesson_id in course.prerequisite_lesson_ids:
        entry = library.lesson_entry(lesson_id)
        record = (store.load(lesson_id, entry.lesson.content_revision)
                  if store is not None and entry is not None else None)
        if record is None or not record.completed:
            missing.append(lesson_id)

    statuses = {}
    done_count = 0
    previous_done = True
    for entry in library.course_lessons(course):
        if entry is None:
            previous_done = False
            continue
        lesson = entry.lesson
        record = (store.load(lesson.lesson_id, lesson.content_revision)
                  if store is not None else None)
        if store is None:
            status = "NEXT"
        elif record and record.completed:
            status = "DONE"
            for step in lesson.steps:
                if step.practice_mode == "independent":
                    outcome = store.load_step_progress(
                        lesson.lesson_id, lesson.content_revision).get(step.step_id)
                    if outcome and outcome.outcome != "independent":
                        status = "REVISIT"
                        break
            done_count += 1
        elif record:
            status = "IN PROGRESS"
        else:
            status = "NEXT" if previous_done else "LATER"
        statuses[lesson.lesson_id] = status
        previous_done = bool(record and record.completed)
    return CourseSummary(statuses, done_count, tuple(missing))
