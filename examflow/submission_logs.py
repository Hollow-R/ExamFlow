import json
import os
from collections import deque


def append_submission_log(app, assignment):
    path = app.config["SUBMISSION_LOG_PATH"]
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    event = {
        "timestamp_utc": assignment.submitted_at.isoformat() + "Z",
        "student_id": assignment.student_id,
        "username": assignment.student.username,
        "exam_id": assignment.exam_id,
        "exam_title": assignment.exam.title,
        "assignment_id": assignment.id,
        "score": assignment.score,
        "maximum_score": len(assignment.exam.exam_questions),
    }
    with open(path, "a", encoding="utf-8") as log_file:
        log_file.write(json.dumps(event, ensure_ascii=False) + "\n")


def read_recent_submission_logs(path, limit=500):
    try:
        with open(path, "r", encoding="utf-8") as log_file:
            lines = deque(enumerate(log_file, start=1), maxlen=limit)
    except FileNotFoundError:
        return []

    events = []
    for line_number, line in lines:
        try:
            event = json.loads(line)
        except ValueError as error:
            raise ValueError(
                "Gönderim logunda geçersiz JSON satırı: {}".format(line_number)
            ) from error
        if not isinstance(event, dict):
            raise ValueError(
                "Gönderim logunda geçersiz kayıt: satır {}".format(line_number)
            )
        events.append(event)
    return list(reversed(events))
