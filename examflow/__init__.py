import os
import secrets

import click
from flask import Flask, abort, jsonify, redirect, render_template, url_for
from flask_login import current_user
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from .extensions import db, login_manager


def create_app(test_config=None):
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    app = Flask(
        __name__,
        instance_relative_config=True,
        template_folder=os.path.join(project_root, "templates"),
        static_folder=os.path.join(project_root, "static"),
    )
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("EXAMFLOW_SECRET_KEY")
        or _load_or_create_secret_key(app.instance_path),
        SQLALCHEMY_DATABASE_URI=os.environ.get(
            "EXAMFLOW_DATABASE_URI", "sqlite:///examflow.db"
        ),
        TEACHER_REGISTRATION_CODE=os.environ.get(
            "EXAMFLOW_TEACHER_REGISTRATION_CODE", "0000"
        ),
        SUBMISSION_LOG_PATH=os.environ.get(
            "EXAMFLOW_SUBMISSION_LOG",
            os.path.join(app.instance_path, "submission_logs.jsonl"),
        ),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        REMEMBER_COOKIE_HTTPONLY=True,
        REMEMBER_COOKIE_SAMESITE="Lax",
    )
    if test_config is not None:
        app.config.update(test_config)

    os.makedirs(app.instance_path, exist_ok=True)
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Devam etmek için giriş yapın."
    login_manager.login_message_category = "warning"

    from .models import User
    from .auth.routes import auth_bp
    from .student.routes import student_bp
    from .teacher.routes import teacher_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(teacher_bp)
    app.register_blueprint(student_bp)

    @app.route("/health")
    def health():
        return jsonify({"service": "ExamFlow", "status": "ok"})

    @app.route("/")
    def index():
        if not current_user.is_authenticated:
            return redirect(url_for("auth.login"))
        if current_user.role == "teacher":
            return redirect(url_for("teacher.dashboard"))
        if current_user.role == "student":
            return redirect(url_for("student.dashboard"))
        abort(403)

    @app.errorhandler(403)
    def forbidden(error):
        return render_template("errors/403.html", error=error), 403

    @app.cli.command("create-user")
    @click.option("--username", prompt=True, help="Oturum açma kullanıcı adı.")
    @click.option("--full-name", prompt="Ad soyad", help="Kullanıcının görünen adı.")
    @click.option(
        "--role",
        type=click.Choice(["teacher", "student"]),
        prompt=True,
        help="Kullanıcı rolü.",
    )
    def create_user(username, full_name, role):
        """Öğretmen veya öğrenci hesabı oluştur."""
        normalized_username = username.strip().lower()
        normalized_name = full_name.strip()
        if not normalized_username or not normalized_name:
            raise click.ClickException("Kullanıcı adı ve ad soyad boş olamaz.")
        if User.query.filter_by(username=normalized_username).first() is not None:
            raise click.ClickException("Bu kullanıcı adı zaten kayıtlı.")

        password = click.prompt(
            "Şifre", hide_input=True, confirmation_prompt=True
        )
        if len(password) < 8:
            raise click.ClickException("Şifre en az 8 karakter olmalıdır.")

        user = User(
            username=normalized_username,
            full_name=normalized_name,
            role=role,
        )
        user.set_password(password)
        db.session.add(user)
        try:
            db.session.commit()
        except IntegrityError as error:
            db.session.rollback()
            raise click.ClickException("Kullanıcı kaydedilemedi.") from error

        click.echo("{} hesabı oluşturuldu.".format(role))

    with app.app_context():
        db.create_all()
        _migrate_question_schema()

    return app


def _load_or_create_secret_key(instance_path):
    os.makedirs(instance_path, exist_ok=True)
    key_path = os.path.join(instance_path, "secret_key")
    try:
        with open(key_path, "r", encoding="ascii") as key_file:
            secret_key = key_file.read().strip()
        if secret_key:
            return secret_key
    except FileNotFoundError:
        pass
    except OSError as error:
        raise RuntimeError("Flask oturum anahtarı okunamadı.") from error

    secret_key = secrets.token_hex(32)
    try:
        with open(key_path, "x", encoding="ascii") as key_file:
            key_file.write(secret_key)
    except FileExistsError:
        try:
            with open(key_path, "r", encoding="ascii") as key_file:
                existing_key = key_file.read().strip()
        except OSError as error:
            raise RuntimeError("Flask oturum anahtarı okunamadı.") from error
        if not existing_key:
            raise RuntimeError("Flask oturum anahtarı boş.")
        return existing_key
    except OSError as error:
        raise RuntimeError("Flask oturum anahtarı kaydedilemedi.") from error
    return secret_key


def _migrate_question_schema():
    if db.engine.dialect.name != "sqlite":
        raise RuntimeError("Şema güncellemesi yalnızca SQLite için yapılandırılmıştır.")

    existing_columns = {
        column["name"] for column in inspect(db.engine).get_columns("questions")
    }
    with db.engine.begin() as connection:
        if "question_type" not in existing_columns:
            connection.execute(
                text(
                    "ALTER TABLE questions ADD COLUMN question_type "
                    "VARCHAR(20) NOT NULL DEFAULT 'multiple_choice'"
                )
            )
        if "expected_answer" not in existing_columns:
            connection.execute(
                text(
                    "ALTER TABLE questions ADD COLUMN expected_answer "
                    "TEXT NOT NULL DEFAULT ''"
                )
            )
