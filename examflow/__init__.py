import os
import secrets

import click
from flask import Flask, abort, redirect, render_template, url_for
from flask_login import current_user
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
        SECRET_KEY=os.environ.get("EXAMFLOW_SECRET_KEY", secrets.token_hex(32)),
        SQLALCHEMY_DATABASE_URI=os.environ.get(
            "EXAMFLOW_DATABASE_URI", "sqlite:///examflow.db"
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

    return app
