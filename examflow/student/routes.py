from datetime import datetime, timedelta, timezone

from flask import abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user

from ..auth.decorators import roles_required
from ..extensions import db
from ..models import Exam, ExamAssignment, StudentAnswer, TextStudentAnswer
from ..submission_logs import append_submission_log
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
            text_answers = []
            invalid_selection = False
            score = 0
            for exam_question in exam.exam_questions:
                question = exam_question.question
                if question.question_type == "classic":
                    field_name = "text_answer_{}".format(exam_question.id)
                    answer_text = request.form.get(field_name, "")
                    if len(answer_text) > 10000:
                        invalid_selection = True
                        break
                    if field_name in request.form:
                        text_answers.append(
                            TextStudentAnswer(
                                exam_question=exam_question,
                                answer_text=answer_text,
                            )
                        )
                    if answer_text.strip().casefold() == question.expected_answer.strip().casefold():
                        score += 1
                    continue

                field_name = "answer_{}".format(exam_question.id)
                raw_option_id = request.form.get(field_name, "")
                if raw_option_id:
                    try:
                        option_id = int(raw_option_id)
                    except ValueError:
                        invalid_selection = True
                        break

                    option = next(
                        (
                            option
                            for option in question.options
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
                flash("Gönderilen yanıtlardan biri geçersiz veya çok uzun.", "danger")
            else:
                assignment.answers = answers
                assignment.text_answers = text_answers
                assignment.score = score
                assignment.submitted_at = now
                db.session.commit()
                try:
                    append_submission_log(current_app, assignment)
                except OSError:
                    current_app.logger.exception(
                        "Sınav gönderimi veritabanına kaydedildi ancak log dosyasına yazılamadı."
                    )
                    flash(
                        "Cevaplar kaydedildi ancak gönderim logu yazılamadı.",
                        "warning",
                    )
                flash("Sınav cevaplarınız kaydedildi.", "success")
                return redirect(url_for("student.take_exam", assignment_id=assignment.id))

    return render_template(
        "student/take_exam.html",
        assignment=assignment,
        exam=exam,
        now=now,
        ends_at=ends_at,
    )
