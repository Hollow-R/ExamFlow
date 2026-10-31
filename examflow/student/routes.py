from flask import render_template

from ..auth.decorators import roles_required
from . import student_bp


@student_bp.route("/")
@roles_required("student")
def dashboard():
    return render_template("student/dashboard.html")
