from flask import render_template

from ..auth.decorators import roles_required
from . import teacher_bp


@teacher_bp.route("/")
@roles_required("teacher")
def dashboard():
    return render_template("teacher/dashboard.html")
