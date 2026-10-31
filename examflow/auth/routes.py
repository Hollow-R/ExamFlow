from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_user, logout_user
from sqlalchemy.exc import IntegrityError

from ..extensions import db
from ..models import User
from . import auth_bp


def _dashboard_endpoint(role):
    if role == "teacher":
        return "teacher.dashboard"
    if role == "student":
        return "student.dashboard"
    return "auth.login"


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for(_dashboard_endpoint(current_user.role)))

    if request.method == "POST":
        username = request.form.get("username", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(username=username).first()
        if user is not None and user.check_password(password):
            login_user(user)
            return redirect(url_for(_dashboard_endpoint(user.role)))

        flash("Kullanıcı adı veya şifre hatalı.", "danger")

    return render_template("auth/login.html")


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for(_dashboard_endpoint(current_user.role)))

    if request.method == "POST":
        username = request.form.get("username", "").strip().lower()
        full_name = request.form.get("full_name", "").strip()
        role = request.form.get("role", "student")
        password = request.form.get("password", "")
        password_confirmation = request.form.get("password_confirmation", "")

        if role not in ("student", "teacher"):
            flash("Geçerli bir hesap türü seçin.", "danger")
        elif not username or not full_name:
            flash("Kullanıcı adı ve ad soyad zorunludur.", "danger")
        elif len(username) > 80 or len(full_name) > 120:
            flash("Kullanıcı adı veya ad soyad izin verilen uzunluğu aşıyor.", "danger")
        elif User.query.filter_by(username=username).first() is not None:
            flash("Bu kullanıcı adı zaten kayıtlı.", "danger")
        elif len(password) < 8 or len(password) > 128:
            flash("Şifre 8 ile 128 karakter arasında olmalıdır.", "danger")
        elif password != password_confirmation:
            flash("Şifreler birbiriyle eşleşmiyor.", "danger")
        else:
            user = User(username=username, full_name=full_name, role=role)
            user.set_password(password)
            db.session.add(user)
            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                flash("Bu kullanıcı adı zaten kayıtlı.", "danger")
            else:
                login_user(user)
                return redirect(url_for(_dashboard_endpoint(user.role)))

    return render_template("auth/register.html")


@auth_bp.route("/logout", methods=["POST"])
def logout():
    if current_user.is_authenticated:
        logout_user()
    return redirect(url_for("auth.login"))
