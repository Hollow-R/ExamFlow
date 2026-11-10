from flask_login import UserMixin
from sqlalchemy import CheckConstraint, UniqueConstraint
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db, login_manager


class User(UserMixin, db.Model):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "role IN ('teacher', 'student')",
            name="ck_users_role",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    full_name = db.Column(db.String(120), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return "<User {}>".format(self.username)


class QuestionCategory(db.Model):
    __tablename__ = "question_categories"
    __table_args__ = (
        UniqueConstraint("teacher_id", "name", name="uq_category_teacher_name"),
    )

    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    name = db.Column(db.String(80), nullable=False)
    teacher = db.relationship("User")


class Question(db.Model):
    __tablename__ = "questions"
    __table_args__ = (
        CheckConstraint(
            "question_type IN ('multiple_choice', 'classic')",
            name="ck_questions_type",
        ),
        CheckConstraint(
            "difficulty IN ('easy', 'medium', 'hard')",
            name="ck_questions_difficulty",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    category_id = db.Column(
        db.Integer, db.ForeignKey("question_categories.id"), nullable=False
    )
    text = db.Column(db.Text, nullable=False)
    difficulty = db.Column(db.String(10), nullable=False)
    question_type = db.Column(
        db.String(20), nullable=False, default="multiple_choice"
    )
    expected_answer = db.Column(db.Text, nullable=False, default="")
    category = db.relationship("QuestionCategory")
    options = db.relationship(
        "QuestionOption",
        backref="question",
        cascade="all, delete-orphan",
        order_by="QuestionOption.id",
    )


class QuestionOption(db.Model):
    __tablename__ = "question_options"

    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey("questions.id"), nullable=False)
    text = db.Column(db.String(500), nullable=False)
    is_correct = db.Column(db.Boolean, nullable=False, default=False)


class Exam(db.Model):
    __tablename__ = "exams"
    __table_args__ = (
        CheckConstraint(
            "duration_minutes BETWEEN 1 AND 480",
            name="ck_exams_duration",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    title = db.Column(db.String(120), nullable=False)
    starts_at = db.Column(db.DateTime, nullable=False)
    duration_minutes = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False)
    exam_questions = db.relationship(
        "ExamQuestion",
        backref="exam",
        cascade="all, delete-orphan",
        order_by="ExamQuestion.position",
    )
    assignments = db.relationship(
        "ExamAssignment",
        backref="exam",
        cascade="all, delete-orphan",
    )


class ExamQuestion(db.Model):
    __tablename__ = "exam_questions"
    __table_args__ = (
        UniqueConstraint("exam_id", "question_id", name="uq_exam_question"),
        UniqueConstraint("exam_id", "position", name="uq_exam_position"),
    )

    id = db.Column(db.Integer, primary_key=True)
    exam_id = db.Column(db.Integer, db.ForeignKey("exams.id"), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey("questions.id"), nullable=False)
    position = db.Column(db.Integer, nullable=False)
    question = db.relationship("Question")


class ExamAssignment(db.Model):
    __tablename__ = "exam_assignments"
    __table_args__ = (
        UniqueConstraint("exam_id", "student_id", name="uq_exam_student"),
    )

    id = db.Column(db.Integer, primary_key=True)
    exam_id = db.Column(db.Integer, db.ForeignKey("exams.id"), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    submitted_at = db.Column(db.DateTime)
    score = db.Column(db.Integer)
    student = db.relationship("User")
    answers = db.relationship(
        "StudentAnswer",
        backref="assignment",
        cascade="all, delete-orphan",
    )
    text_answers = db.relationship(
        "TextStudentAnswer",
        backref="assignment",
        cascade="all, delete-orphan",
    )


class StudentAnswer(db.Model):
    __tablename__ = "student_answers"
    __table_args__ = (
        UniqueConstraint(
            "assignment_id", "exam_question_id", name="uq_assignment_answer"
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    assignment_id = db.Column(
        db.Integer, db.ForeignKey("exam_assignments.id"), nullable=False
    )
    exam_question_id = db.Column(
        db.Integer, db.ForeignKey("exam_questions.id"), nullable=False
    )
    selected_option_id = db.Column(
        db.Integer, db.ForeignKey("question_options.id"), nullable=False
    )
    exam_question = db.relationship("ExamQuestion")
    selected_option = db.relationship("QuestionOption")


class TextStudentAnswer(db.Model):
    __tablename__ = "text_student_answers"
    __table_args__ = (
        UniqueConstraint(
            "assignment_id", "exam_question_id", name="uq_assignment_text_answer"
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    assignment_id = db.Column(
        db.Integer, db.ForeignKey("exam_assignments.id"), nullable=False
    )
    exam_question_id = db.Column(
        db.Integer, db.ForeignKey("exam_questions.id"), nullable=False
    )
    answer_text = db.Column(db.Text, nullable=False)
    exam_question = db.relationship("ExamQuestion")


@login_manager.user_loader
def load_user(user_id):
    try:
        user_id = int(user_id)
    except (TypeError, ValueError):
        return None
    return db.session.get(User, user_id)
