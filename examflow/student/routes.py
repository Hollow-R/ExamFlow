from datetime import datetime, timedelta, timezone

from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user

from ..auth.decorators import roles_required
from ..extensions import db
from ..models import Exam, ExamAssignment, StudentAnswer
from . import student_bp


def _assignment_for_current_student(assignment_id):
    assignment = ExamAssignment.query.filter_by(
        id=assignment_id,
        student_id=current_user.id,
    ).first()
    if assignment is None:
        abort(404)
    return assignment


def _exam_ends_at(assignment):
    return assignment.exam.starts_at + timedelta(
        minutes=assignment.exam.duration_minutes
    )


def _utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


@student_bp.route("/")
@roles_required("student")
def dashboard():
    assignments = (
        ExamAssignment.query.filter_by(student_id=current_user.id)
        .join(ExamAssignment.exam)
        .order_by(Exam.starts_at)
        .all()
    )
    now = _utc_now()
    return render_template(
        "student/dashboard.html",
        assignments=assignments,
        now=now,
        timedelta=timedelta,
    )


@student_bp.route("/exams/<int:assignment_id>", methods=["GET", "POST"])
@roles_required("student")
def take_exam(assignment_id):
    assignment = _assignment_for_current_student(assignment_id)
    exam = assignment.exam
    now = _utc_now()
    ends_at = _exam_ends_at(assignment)

    if request.method == "POST":
        if assignment.submitted_at is not None:
            flash("Bu sınavın cevapları daha önce gönderildi.", "warning")
        elif now < exam.starts_at:
            flash("Sınav henüz başlamadı.", "warning")
        elif now >= ends_at:
            flash("Sınav süresi dolduğu için cevap gönderilemedi.", "danger")
        else:
            answers = []
            invalid_selection = False
            score = 0
            for exam_question in exam.exam_questions:
                field_name = "answer_{}".format(exam_question.id)
                raw_option_id = request.form.get(field_name, "")
                if not raw_option_id:
                    continue
                try:
                    option_id = int(raw_option_id)
                except ValueError:
                    invalid_selection = True
                    break

                option = next(
                    (
                        option
                        for option in exam_question.question.options
                        if option.id == option_id
                    ),
                    None,
                )
                if option is None:
                    invalid_selection = True
                    break
                answers.append(
                    StudentAnswer(
                        exam_question=exam_question,
                        selected_option=option,
                    )
                )
                if option.is_correct:
                    score += 1

            if invalid_selection:
                flash("Gönderilen yanıtlardan biri geçersiz.", "danger")
            else:
                assignment.answers = answers
                assignment.score = score
                assignment.submitted_at = now
                db.session.commit()
                flash("Sınav cevaplarınız kaydedildi.", "success")
                return redirect(url_for("student.take_exam", assignment_id=assignment.id))

    return render_template(
        "student/take_exam.html",
        assignment=assignment,
        exam=exam,
        now=now,
        ends_at=ends_at,
    )
