import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

from sqlalchemy import inspect

from examflow import _migrate_question_schema, create_app
from examflow.extensions import db
from examflow.models import (
    Exam,
    ExamAssignment,
    ExamQuestion,
    Question,
    QuestionCategory,
    QuestionOption,
    User,
)


class ExamWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(
            {
                "TESTING": True,
                "SECRET_KEY": "test-secret",
                "SQLALCHEMY_DATABASE_URI": "sqlite://",
            }
        )
        self.log_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.log_directory.cleanup)
        self.app.config["SUBMISSION_LOG_PATH"] = os.path.join(
            self.log_directory.name,
            "submission_logs.jsonl",
        )
        self.client = self.app.test_client()
        with self.app.app_context():
            db.create_all()
            self.teacher = User(
                username="teacher",
                full_name="Test Teacher",
                role="teacher",
            )
            self.teacher.set_password("teacher-pass")
            self.student = User(
                username="student",
                full_name="Test Student",
                role="student",
            )
            self.student.set_password("student-pass")
            self.other_student = User(
                username="other-student",
                full_name="Other Student",
                role="student",
            )
            self.other_student.set_password("student-pass")
            self.category = QuestionCategory(teacher=self.teacher, name="Matematik")
            db.session.add_all(
                [self.teacher, self.student, self.other_student, self.category]
            )
            db.session.commit()
            self.question = Question(
                teacher_id=self.teacher.id,
                category_id=self.category.id,
                text="2 + 2 kaçtır?",
                difficulty="easy",
            )
            self.question.options = [
                QuestionOption(text="3", is_correct=False),
                QuestionOption(text="4", is_correct=True),
                QuestionOption(text="5", is_correct=False),
                QuestionOption(text="6", is_correct=False),
            ]
            db.session.add(self.question)
            db.session.commit()
            self.question_id = self.question.id
            self.category_id = self.category.id
            self.teacher_id = self.teacher.id
            self.student_id = self.student.id
            self.other_student_id = self.other_student.id

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def login(self, username, password="student-pass"):
        response = self.client.post(
            "/auth/login",
            data={"username": username, "password": password},
        )
        self.assertEqual(response.status_code, 302)

    def create_assignment(self, starts_at=None, duration_minutes=30, question_ids=None):
        if starts_at is None:
            starts_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(
                minutes=1
            )
        with self.app.app_context():
            questions = [
                db.session.get(Question, question_id)
                for question_id in (question_ids or [self.question_id])
            ]
            students = [
                db.session.get(User, self.student_id),
                db.session.get(User, self.other_student_id),
            ]
            exam = Exam(
                teacher_id=questions[0].teacher_id,
                title="Ara Sınav",
                starts_at=starts_at,
                duration_minutes=duration_minutes,
                created_at=datetime.now(timezone.utc).replace(tzinfo=None),
            )
            exam.exam_questions = [
                ExamQuestion(question=question, position=index)
                for index, question in enumerate(questions)
            ]
            exam.assignments = [ExamAssignment(student=student) for student in students]
            db.session.add(exam)
            db.session.commit()
            return exam.assignments[0].id, exam.assignments[1].id

    def test_teacher_can_create_category_and_question(self):
        self.login("teacher", "teacher-pass")
        response = self.client.post(
            "/teacher/categories",
            data={"name": "Fizik"},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)

        with self.app.app_context():
            category = QuestionCategory.query.filter_by(name="Fizik").one()
            category_id = category.id

        response = self.client.post(
            "/teacher/questions",
            data={
                "text": "Işık hızı hangi sembolle gösterilir?",
                "category_id": str(category_id),
                "difficulty": "medium",
                "option_text": ["x", "c", "v", "t"],
                "correct_option": "1",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            question = Question.query.filter_by(
                text="Işık hızı hangi sembolle gösterilir?"
            ).one()
            self.assertEqual(question.difficulty, "medium")
            self.assertEqual(question.category.name, "Fizik")
            self.assertEqual(
                [option.text for option in question.options if option.is_correct],
                ["c"],
            )

    def test_teacher_can_create_classic_question(self):
        self.login("teacher", "teacher-pass")
        response = self.client.post(
            "/teacher/questions",
            data={
                "text": "Türkiye'nin başkenti neresidir?",
                "category_id": str(self.category_id),
                "difficulty": "easy",
                "question_type": "classic",
                "expected_answer": "Ankara",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            question = Question.query.filter_by(
                text="Türkiye'nin başkenti neresidir?"
            ).one()
            self.assertEqual(question.question_type, "classic")
            self.assertEqual(question.expected_answer, "Ankara")
            self.assertEqual(question.options, [])

    def test_existing_question_table_migrates_without_losing_rows(self):
        with self.app.app_context():
            db.drop_all()
            with db.engine.begin() as connection:
                connection.exec_driver_sql(
                    "CREATE TABLE questions (id INTEGER PRIMARY KEY, text TEXT)"
                )
                connection.exec_driver_sql(
                    "INSERT INTO questions (id, text) VALUES (1, 'Legacy question')"
                )

            _migrate_question_schema()

            columns = {
                column["name"]
                for column in inspect(db.engine).get_columns("questions")
            }
            self.assertIn("question_type", columns)
            self.assertIn("expected_answer", columns)
            with db.engine.connect() as connection:
                row = connection.exec_driver_sql(
                    "SELECT text, question_type, expected_answer FROM questions WHERE id = 1"
                ).one()
            self.assertEqual(row, ("Legacy question", "multiple_choice", ""))

    def test_student_cannot_access_teacher_question_management(self):
        self.login("student")
        self.assertEqual(self.client.get("/teacher/questions").status_code, 403)
        self.assertEqual(
            self.client.post("/teacher/categories", data={"name": "Gizli"}).status_code,
            403,
        )

    def test_teacher_publishes_scheduled_exam_to_all_students(self):
        self.login("teacher", "teacher-pass")
        starts_at = (
            datetime.now(timezone.utc) + timedelta(days=1)
        ).replace(microsecond=0)
        response = self.client.post(
            "/teacher/exams",
            data={
                "title": "Planlı sınav",
                "starts_at_utc": starts_at.isoformat(),
                "duration_minutes": "45",
                "question_ids": [str(self.question_id)],
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("2 öğrenciye atandı.".encode("utf-8"), response.data)
        with self.app.app_context():
            exam = Exam.query.filter_by(title="Planlı sınav").one()
            self.assertEqual(exam.duration_minutes, 45)
            self.assertEqual(exam.exam_questions[0].question_id, self.question_id)
            self.assertEqual(len(exam.assignments), 2)

    def test_exam_creation_rejects_non_future_start_time(self):
        self.login("teacher", "teacher-pass")
        past = datetime.now(timezone.utc) - timedelta(minutes=1)
        response = self.client.post(
            "/teacher/exams",
            data={
                "title": "Geçmiş sınav",
                "starts_at_utc": past.isoformat(),
                "duration_minutes": "30",
                "question_ids": [str(self.question_id)],
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "başlangıç zamanı gelecekte".encode("utf-8"),
            response.data,
        )
        with self.app.app_context():
            self.assertEqual(Exam.query.count(), 0)

    def test_student_can_submit_answers_and_score_is_calculated(self):
        assignment_id = self.create_assignment()[0]
        self.login("student")
        response = self.client.get("/student/exams/{}".format(assignment_id))
        self.assertEqual(response.status_code, 200)
        self.assertIn("2 + 2 kaçtır?".encode("utf-8"), response.data)
        self.assertNotIn(b"Do\xc4\x9fru cevap", response.data)

        with self.app.app_context():
            exam_question = ExamQuestion.query.one()
            correct_option = QuestionOption.query.filter_by(
                question_id=self.question_id,
                is_correct=True,
            ).one()
            exam_question_id = exam_question.id
            correct_option_id = correct_option.id

        response = self.client.post(
            "/student/exams/{}".format(assignment_id),
            data={"answer_{}".format(exam_question_id): str(correct_option_id)},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("Cevaplarınız gönderildi".encode("utf-8"), response.data)
        with self.app.app_context():
            assignment = db.session.get(ExamAssignment, assignment_id)
            self.assertEqual(assignment.score, 1)
            self.assertIsNotNone(assignment.submitted_at)
            self.assertEqual(len(assignment.answers), 1)

    def test_classic_answer_uses_case_and_outer_whitespace_insensitive_exact_match(self):
        self.login("teacher", "teacher-pass")
        response = self.client.post(
            "/teacher/questions",
            data={
                "text": "Türkiye'nin başkenti neresidir?",
                "category_id": str(self.category_id),
                "difficulty": "easy",
                "question_type": "classic",
                "expected_answer": " Ankara ",
            },
        )
        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            classic_question = Question.query.filter_by(
                question_type="classic"
            ).one()
            classic_question_id = classic_question.id

        assignment_id, _ = self.create_assignment(
            question_ids=[self.question_id, classic_question_id]
        )
        with self.app.app_context():
            exam_questions = ExamQuestion.query.order_by(ExamQuestion.position).all()
            mc_question_id = exam_questions[0].id
            classic_exam_question_id = exam_questions[1].id
            correct_option_id = QuestionOption.query.filter_by(
                question_id=self.question_id,
                is_correct=True,
            ).one().id

        self.client.post("/auth/logout")
        self.login("student")
        exam_page = self.client.get("/student/exams/{}".format(assignment_id))
        self.assertIn("başkenti neresidir".encode("utf-8"), exam_page.data)
        self.assertNotIn(b"Ankara", exam_page.data)
        response = self.client.post(
            "/student/exams/{}".format(assignment_id),
            data={
                "answer_{}".format(mc_question_id): str(correct_option_id),
                "text_answer_{}".format(classic_exam_question_id): "  aNkArA ",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            assignment = db.session.get(ExamAssignment, assignment_id)
            self.assertEqual(assignment.score, 2)
            self.assertEqual(assignment.text_answers[0].answer_text, "  aNkArA ")

        self.client.post("/auth/logout")
        self.login("teacher", "teacher-pass")
        with self.app.app_context():
            exam_id = db.session.get(ExamAssignment, assignment_id).exam_id
        results = self.client.get("/teacher/exams/{}/results".format(exam_id))
        self.assertIn("Öğrenci yanıtı".encode("utf-8"), results.data)
        self.assertIn("aNkArA".encode("utf-8"), results.data)

    def test_student_registration_receives_future_exams_only(self):
        future_starts = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(
            days=1
        )
        self.create_assignment(starts_at=future_starts)
        past_starts = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(
            days=1
        )
        self.create_assignment(starts_at=past_starts)

        response = self.client.post(
            "/auth/register",
            data={
                "full_name": "Late Student",
                "username": "late-student",
                "password": "student-password",
                "password_confirmation": "student-password",
                "role": "student",
            },
        )
        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            new_student = User.query.filter_by(username="late-student").one()
            assignments = ExamAssignment.query.filter_by(
                student_id=new_student.id
            ).all()
            self.assertEqual(len(assignments), 1)
            self.assertEqual(assignments[0].exam.starts_at, future_starts)

    def test_health_endpoint_is_available_without_login(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["service"], "ExamFlow")
    def test_student_cannot_open_another_students_assignment(self):
        other_assignment_id = self.create_assignment()[1]
        self.login("student")
        self.assertEqual(
            self.client.get(
                "/student/exams/{}".format(other_assignment_id)
            ).status_code,
            404,
        )

    def test_student_cannot_submit_an_option_from_another_question(self):
        assignment_id = self.create_assignment()[0]
        with self.app.app_context():
            exam_question = ExamQuestion.query.one()
            other_question = Question(
                teacher_id=self.teacher_id,
                category_id=self.category_id,
                text="Başka soru",
                difficulty="hard",
            )
            other_question.options = [
                QuestionOption(text="Yanıt", is_correct=True),
                QuestionOption(text="Diğer", is_correct=False),
            ]
            db.session.add(other_question)
            db.session.commit()
            other_option_id = other_question.options[0].id
            exam_question_id = exam_question.id

        self.login("student")
        response = self.client.post(
            "/student/exams/{}".format(assignment_id),
            data={"answer_{}".format(exam_question_id): str(other_option_id)},
            follow_redirects=True,
        )
        self.assertIn("yanıtlardan biri geçersiz".encode("utf-8"), response.data)
        with self.app.app_context():
            assignment = db.session.get(ExamAssignment, assignment_id)
            self.assertIsNone(assignment.submitted_at)
            self.assertEqual(len(assignment.answers), 0)

    def test_server_rejects_submission_after_exam_deadline(self):
        starts_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(
            hours=1
        )
        assignment_id = self.create_assignment(
            starts_at=starts_at,
            duration_minutes=10,
        )[0]
        with self.app.app_context():
            exam_question = ExamQuestion.query.one()
            correct_option = QuestionOption.query.filter_by(
                question_id=self.question_id,
                is_correct=True,
            ).one()
            exam_question_id = exam_question.id
            correct_option_id = correct_option.id
        self.login("student")
        response = self.client.post(
            "/student/exams/{}".format(assignment_id),
            data={"answer_{}".format(exam_question_id): str(correct_option_id)},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("Sınav süresi dolduğu".encode("utf-8"), response.data)
        with self.app.app_context():
            assignment = db.session.get(ExamAssignment, assignment_id)
            self.assertIsNone(assignment.submitted_at)
            self.assertIsNone(assignment.score)

    def test_teacher_can_view_per_student_exam_results(self):
        assignment_id = self.create_assignment()[0]
        self.login("teacher", "teacher-pass")
        with self.app.app_context():
            assignment = db.session.get(ExamAssignment, assignment_id)
            exam_id = assignment.exam_id
        response = self.client.get("/teacher/exams/{}/results".format(exam_id))
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Test Student", response.data)
        self.assertIn(b"Other Student", response.data)

    def test_submission_is_written_to_log_and_visible_to_teacher_only(self):
        assignment_id = self.create_assignment()[0]
        with self.app.app_context():
            exam_question = ExamQuestion.query.one()
            correct_option = QuestionOption.query.filter_by(
                question_id=self.question_id,
                is_correct=True,
            ).one()
            exam_question_id = exam_question.id
            correct_option_id = correct_option.id

        self.login("student")
        response = self.client.post(
            "/student/exams/{}".format(assignment_id),
            data={"answer_{}".format(exam_question_id): str(correct_option_id)},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)

        with open(self.app.config["SUBMISSION_LOG_PATH"], "r", encoding="utf-8") as log_file:
            log_event = json.loads(log_file.readline())
        self.assertEqual(log_event["username"], "student")
        self.assertEqual(log_event["exam_title"], "Ara Sınav")
        self.assertEqual(log_event["score"], 1)

        self.assertEqual(self.client.get("/teacher/logs").status_code, 403)
        self.client.post("/auth/logout")
        self.login("teacher", "teacher-pass")
        log_page = self.client.get("/teacher/logs")
        self.assertEqual(log_page.status_code, 200)
        self.assertIn(b"student", log_page.data)
        self.assertIn(b"Ara S", log_page.data)


if __name__ == "__main__":
    unittest.main()
