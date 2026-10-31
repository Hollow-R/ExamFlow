from datetime import datetime, timedelta, timezone

from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy.exc import IntegrityError

from ..auth.decorators import roles_required
from ..extensions import db
from ..models import (
    Exam,
    ExamAssignment,
    ExamQuestion,
    Question,
    QuestionCategory,
    QuestionOption,
    User,
)
from . import teacher_bp


DIFFICULTIES = ("easy", "medium", "hard")
MAX_OPTIONS = 4
MIN_OPTIONS = 2


def _utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _owned_question(question_id):
    question = Question.query.filter_by(
        id=question_id,
        teacher_id=current_user.id,
    ).first()
    if question is None:
        abort(404)
    return question


def _question_used_in_exam(question_id):
    return (
        db.session.query(ExamQuestion.id)
        .join(Exam)
        .filter(
            ExamQuestion.question_id == question_id,
            Exam.teacher_id == current_user.id,
        )
        .first()
        is not None
    )


def _question_form_values():
    text = request.form.get("text", "").strip()
    category_id = request.form.get("category_id", type=int)
    difficulty = request.form.get("difficulty", "")
    raw_options = [value.strip() for value in request.form.getlist("option_text")]
    correct_option = request.form.get("correct_option", type=int)
    if (
        correct_option is not None
        and 0 <= correct_option < len(raw_options)
        and raw_options[correct_option]
    ):
        correct_option = sum(
            1 for value in raw_options[:correct_option] if value
        )
    elif correct_option is not None:
        correct_option = None
    options = [value for value in raw_options if value]
    return text, category_id, difficulty, options, correct_option


def _validate_question_values(text, category_id, difficulty, options, correct_option):
    if not text:
        return "Soru metni zorunludur."
    category = QuestionCategory.query.filter_by(
        id=category_id,
        teacher_id=current_user.id,
    ).first()
    if category is None:
        return "Geçerli bir kategori seçin."
    if difficulty not in DIFFICULTIES:
        return "Geçerli bir zorluk seviyesi seçin."
    if not MIN_OPTIONS <= len(options) <= MAX_OPTIONS:
        return "Bir soru 2 ile 4 arasında dolu şık içermelidir."
    if correct_option is None or not 0 <= correct_option < len(options):
        return "Doğru cevabı şıklardan seçin."
    return None


@teacher_bp.route("/")
@roles_required("teacher")
def dashboard():
    question_count = Question.query.filter_by(teacher_id=current_user.id).count()
    exam_count = Exam.query.filter_by(teacher_id=current_user.id).count()
    return render_template(
        "teacher/dashboard.html",
        question_count=question_count,
        exam_count=exam_count,
    )


@teacher_bp.route("/questions", methods=["GET", "POST"])
@roles_required("teacher")
def questions():
    categories = QuestionCategory.query.filter_by(
        teacher_id=current_user.id
    ).order_by(QuestionCategory.name).all()
    form_text = ""
    form_category_id = None
    form_difficulty = "easy"
    form_options = []
    form_correct_option = None

    if request.method == "POST":
        text, category_id, difficulty, options, correct_option = _question_form_values()
        form_text = text
        form_category_id = category_id
        form_difficulty = difficulty
        form_options = request.form.getlist("option_text")
        form_correct_option = request.form.get("correct_option", type=int)
        error = _validate_question_values(
            text, category_id, difficulty, options, correct_option
        )
        if error:
            flash(error, "danger")
        else:
            question = Question(
                teacher_id=current_user.id,
                category_id=category_id,
                text=text,
                difficulty=difficulty,
            )
            question.options = [
                QuestionOption(text=option, is_correct=index == correct_option)
                for index, option in enumerate(options)
            ]
            db.session.add(question)
            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                flash("Soru kaydedilemedi. Bilgileri kontrol edip yeniden deneyin.", "danger")
            else:
                flash("Soru soru bankasına eklendi.", "success")
                return redirect(url_for("teacher.questions"))

    question_list = (
        Question.query.filter_by(teacher_id=current_user.id)
        .order_by(Question.id.desc())
        .all()
    )
    return render_template(
        "teacher/questions.html",
        categories=categories,
        questions=question_list,
        difficulties=DIFFICULTIES,
        form_text=form_text,
        form_category_id=form_category_id,
        form_difficulty=form_difficulty,
        form_options=form_options,
        form_correct_option=form_correct_option,
    )


@teacher_bp.route("/categories", methods=["POST"])
@roles_required("teacher")
def create_category():
    name = request.form.get("name", "").strip()
    if not name or len(name) > 80:
        flash("Kategori adı 1 ile 80 karakter arasında olmalıdır.", "danger")
    elif QuestionCategory.query.filter_by(
        teacher_id=current_user.id,
        name=name,
    ).first() is not None:
        flash("Bu kategori zaten mevcut.", "danger")
    else:
        db.session.add(QuestionCategory(teacher_id=current_user.id, name=name))
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash("Bu kategori zaten mevcut.", "danger")
        else:
            flash("Kategori eklendi.", "success")
    return redirect(url_for("teacher.questions"))


@teacher_bp.route("/questions/<int:question_id>/edit", methods=["GET", "POST"])
@roles_required("teacher")
def edit_question(question_id):
    question = _owned_question(question_id)
    if _question_used_in_exam(question_id):
        flash("Yayımlanmış sınavlardaki sorular değiştirilemez.", "warning")
        return redirect(url_for("teacher.questions"))

    categories = QuestionCategory.query.filter_by(
        teacher_id=current_user.id
    ).order_by(QuestionCategory.name).all()
    form_text = None
    form_category_id = None
    form_difficulty = None
    form_options = None
    form_correct_option = None

    if request.method == "POST":
        text, category_id, difficulty, options, correct_option = _question_form_values()
        form_text = text
        form_category_id = category_id
        form_difficulty = difficulty
        form_options = request.form.getlist("option_text")
        form_correct_option = request.form.get("correct_option", type=int)
        error = _validate_question_values(
            text, category_id, difficulty, options, correct_option
        )
        if error:
            flash(error, "danger")
        else:
            question.text = text
            question.category_id = category_id
            question.difficulty = difficulty
            question.options = [
                QuestionOption(text=option, is_correct=index == correct_option)
                for index, option in enumerate(options)
            ]
            db.session.commit()
            flash("Soru güncellendi.", "success")
            return redirect(url_for("teacher.questions"))

    return render_template(
        "teacher/question_form.html",
        categories=categories,
        difficulties=DIFFICULTIES,
        question=question,
        form_text=form_text,
        form_category_id=form_category_id,
        form_difficulty=form_difficulty,
        form_options=form_options,
        form_correct_option=form_correct_option,
    )


@teacher_bp.route("/questions/<int:question_id>/delete", methods=["POST"])
@roles_required("teacher")
def delete_question(question_id):
    question = _owned_question(question_id)
    exam_links = ExamQuestion.query.filter_by(question_id=question_id).all()
    if any(link.exam.teacher_id == current_user.id for link in exam_links):
        flash("Bir sınavda kullanılan soru silinemez.", "warning")
    else:
        db.session.delete(question)
        db.session.commit()
        flash("Soru silindi.", "success")
    return redirect(url_for("teacher.questions"))


@teacher_bp.route("/exams", methods=["GET", "POST"])
@roles_required("teacher")
def exams():
    questions = (
        Question.query.filter_by(teacher_id=current_user.id)
        .order_by(Question.id.desc())
        .all()
    )
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        starts_at_value = request.form.get("starts_at_utc", "")
        duration_minutes = request.form.get("duration_minutes", type=int)
        question_ids = request.form.getlist("question_ids", type=int)
        unique_question_ids = list(dict.fromkeys(question_ids))

        if not title or len(title) > 120:
            flash("Sınav adı 1 ile 120 karakter arasında olmalıdır.", "danger")
        elif duration_minutes is None or not 1 <= duration_minutes <= 480:
            flash("Sınav süresi 1 ile 480 dakika arasında olmalıdır.", "danger")
        elif not unique_question_ids:
            flash("Sınava en az bir soru ekleyin.", "danger")
        else:
            try:
                starts_at = datetime.fromisoformat(
                    starts_at_value.replace("Z", "+00:00")
                )
                if starts_at.tzinfo is None:
                    raise ValueError("UTC timezone is required")
                starts_at = starts_at.astimezone(timezone.utc).replace(tzinfo=None)
            except (TypeError, ValueError):
                starts_at = None

            if starts_at is None or starts_at <= _utc_now():
                flash("Sınav başlangıç zamanı gelecekte olmalıdır.", "danger")
            else:
                question_by_id = {
                    question.id: question
                    for question in Question.query.filter(
                        Question.teacher_id == current_user.id,
                        Question.id.in_(unique_question_ids),
                    ).all()
                }
                selected_questions = [
                    question_by_id[question_id]
                    for question_id in unique_question_ids
                    if question_id in question_by_id
                ]
                students = User.query.filter_by(role="student").order_by(User.id).all()
                if len(selected_questions) != len(unique_question_ids):
                    flash("Seçilen sorulardan biri size ait değil veya bulunamadı.", "danger")
                elif not students:
                    flash("Sınavı atamak için kayıtlı öğrenci bulunamadı.", "danger")
                else:
                    exam = Exam(
                        teacher_id=current_user.id,
                        title=title,
                        starts_at=starts_at,
                        duration_minutes=duration_minutes,
                        created_at=_utc_now(),
                    )
                    exam.exam_questions = [
                        ExamQuestion(question=question, position=index)
                        for index, question in enumerate(selected_questions)
                    ]
                    exam.assignments = [
                        ExamAssignment(student=student) for student in students
                    ]
                    db.session.add(exam)
                    try:
                        db.session.commit()
                    except IntegrityError:
                        db.session.rollback()
                        flash("Sınav kaydedilemedi. Lütfen tekrar deneyin.", "danger")
                    else:
                        flash(
                            "Sınav yayımlandı ve {} öğrenciye atandı.".format(
                                len(students)
                            ),
                            "success",
                        )
                        return redirect(url_for("teacher.exams"))

    exam_list = (
        Exam.query.filter_by(teacher_id=current_user.id)
        .order_by(Exam.starts_at.desc())
        .all()
    )
    return render_template(
        "teacher/exams.html",
        questions=questions,
        exams=exam_list,
        now=_utc_now(),
        student_count=User.query.filter_by(role="student").count(),
    )


@teacher_bp.route("/exams/<int:exam_id>/results")
@roles_required("teacher")
def exam_results(exam_id):
    exam = Exam.query.filter_by(
        id=exam_id,
        teacher_id=current_user.id,
    ).first_or_404()
    assignments = (
        ExamAssignment.query.filter_by(exam_id=exam.id)
        .join(User, ExamAssignment.student_id == User.id)
        .order_by(User.full_name)
        .all()
    )
    return render_template(
        "teacher/results.html",
        exam=exam,
        assignments=assignments,
        now=_utc_now(),
        ends_at=exam.starts_at + timedelta(minutes=exam.duration_minutes),
    )
