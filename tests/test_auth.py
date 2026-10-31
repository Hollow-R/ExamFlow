import unittest

from examflow import create_app
from examflow.extensions import db
from examflow.models import User


class AuthenticationTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(
            {
                "TESTING": True,
                "SECRET_KEY": "test-secret",
                "SQLALCHEMY_DATABASE_URI": "sqlite://",
            }
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
            db.session.add_all([self.teacher, self.student])
            db.session.commit()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def test_password_is_hashed(self):
        with self.app.app_context():
            teacher = User.query.filter_by(username="teacher").one()
            self.assertNotEqual(teacher.password_hash, "teacher-pass")
            self.assertTrue(teacher.check_password("teacher-pass"))
            self.assertFalse(teacher.check_password("wrong-password"))

    def test_login_redirects_to_role_dashboard(self):
        response = self.client.post(
            "/auth/login",
            data={"username": "TEACHER", "password": "teacher-pass"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/teacher/")

        response = self.client.get("/teacher/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Test Teacher", response.data)

    def test_invalid_login_does_not_authenticate(self):
        response = self.client.post(
            "/auth/login",
            data={"username": "teacher", "password": "incorrect"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("Kullanıcı adı veya şifre hatalı.".encode("utf-8"), response.data)
        self.assertEqual(self.client.get("/teacher/").status_code, 302)

    def test_student_can_register_with_hashed_password(self):
        response = self.client.post(
            "/auth/register",
            data={
                "full_name": "New Student",
                "username": "NEW-STUDENT",
                "password": "new-password",
                "password_confirmation": "new-password",
                "role": "student",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/student/")
        self.assertEqual(self.client.get("/student/").status_code, 200)

        with self.app.app_context():
            user = User.query.filter_by(username="new-student").one()
            self.assertEqual(user.role, "student")
            self.assertNotEqual(user.password_hash, "new-password")
            self.assertTrue(user.check_password("new-password"))

    def test_registration_rejects_duplicate_username(self):
        response = self.client.post(
            "/auth/register",
            data={
                "full_name": "Another Student",
                "username": "TEACHER",
                "password": "new-password",
                "password_confirmation": "new-password",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("Bu kullanıcı adı zaten kayıtlı.".encode("utf-8"), response.data)
        with self.app.app_context():
            self.assertEqual(User.query.filter_by(username="teacher").count(), 1)

    def test_registration_validates_password_and_role(self):
        response = self.client.post(
            "/auth/register",
            data={
                "full_name": "New User",
                "username": "new-user",
                "password": "short",
                "password_confirmation": "not-matching",
                "role": "invalid",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "Geçerli bir hesap türü seçin.".encode("utf-8"),
            response.data,
        )
        with self.app.app_context():
            self.assertIsNone(User.query.filter_by(username="new-user").first())

        response = self.client.post(
            "/auth/register",
            data={
                "full_name": "New User",
                "username": "new-user",
                "password": "long-enough",
                "password_confirmation": "different",
                "role": "student",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "Şifreler birbiriyle eşleşmiyor.".encode("utf-8"),
            response.data,
        )

    def test_teacher_can_register_without_invitation_code(self):
        response = self.client.post(
            "/auth/register",
            data={
                "full_name": "New Teacher",
                "username": "new-teacher",
                "password": "long-enough",
                "password_confirmation": "long-enough",
                "role": "teacher",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/teacher/")
        self.assertEqual(self.client.get("/teacher/").status_code, 200)

        with self.app.app_context():
            user = User.query.filter_by(username="new-teacher").one()
            self.assertEqual(user.role, "teacher")
            self.assertTrue(user.check_password("long-enough"))

    def test_authenticated_user_cannot_register_another_account(self):
        self.client.post(
            "/auth/login",
            data={"username": "student", "password": "student-pass"},
        )
        response = self.client.get("/auth/register")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/student/")

    def test_roles_cannot_access_other_dashboard(self):
        response = self.client.post(
            "/auth/login",
            data={"username": "student", "password": "student-pass"},
        )
        self.assertEqual(response.headers["Location"], "/student/")
        self.assertEqual(self.client.get("/student/").status_code, 200)
        self.assertEqual(self.client.get("/teacher/").status_code, 403)

    def test_logout_requires_post_and_clears_session(self):
        self.client.post(
            "/auth/login",
            data={"username": "student", "password": "student-pass"},
        )
        self.assertEqual(self.client.get("/auth/logout").status_code, 405)
        self.assertEqual(self.client.post("/auth/logout").status_code, 302)
        self.assertEqual(self.client.get("/student/").status_code, 302)

    def test_create_user_command_hashes_password(self):
        result = self.app.test_cli_runner().invoke(
            args=[
                "create-user",
                "--username",
                "new-student",
                "--full-name",
                "New Student",
                "--role",
                "student",
            ],
            input="new-password\nnew-password\n",
        )
        self.assertEqual(result.exit_code, 0, result.output)
        with self.app.app_context():
            user = User.query.filter_by(username="new-student").one()
            self.assertEqual(user.role, "student")
            self.assertTrue(user.check_password("new-password"))
