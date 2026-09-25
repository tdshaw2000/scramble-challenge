"""Read-only admin area for browsing past challenges, behind a single password."""

from functools import wraps

from flask import (
    Blueprint,
    abort,
    current_app,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash

bp = Blueprint("admin", __name__, url_prefix="/admin")


@bp.before_request
def only_when_configured():
    config = current_app.config
    if not (config["ADMIN_PASSWORD_HASH"] and config["SECRET_KEY"]):
        abort(404)


def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not session.get("admin"):
            return redirect(url_for("admin.login"))
        return view(*args, **kwargs)

    return wrapper


@bp.get("/login")
def login():
    return render_template("admin/login.html")


@bp.post("/login")
def login_submit():
    password = request.form.get("password", "")
    if not check_password_hash(current_app.config["ADMIN_PASSWORD_HASH"], password):
        return render_template("admin/login.html", error="Wrong password."), 401
    session.clear()
    session.permanent = True
    session["admin"] = True
    return redirect(url_for("admin.home"))


@bp.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("admin.login"))


@bp.get("")
@login_required
def home():
    return render_template("admin/home.html")
