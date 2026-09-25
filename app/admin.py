"""Read-only admin area for browsing past challenges, behind a single password."""

from datetime import UTC, datetime
from functools import wraps
from zoneinfo import ZoneInfo

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

from app.extensions import db
from app.models import Challenge, ChallengeStatus

bp = Blueprint("admin", __name__, url_prefix="/admin")

PAGE_SIZE = 50
UK = ZoneInfo("Europe/London")
STATUS_LABELS = {
    ChallengeStatus.WAITING: "Waiting",
    ChallengeStatus.ROUND_ACTIVE: "Round in progress",
    ChallengeStatus.ROUND_RESULTS: "Showing results",
    ChallengeStatus.ENDED: "Ended",
}


@bp.app_template_filter("uk_time")
def uk_time(moment: datetime) -> str:
    # SQLite hands datetimes back without a timezone; they were stored as UTC.
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return moment.astimezone(UK).strftime("%-d %b %Y, %H:%M")


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
    page = db.paginate(
        db.select(Challenge).order_by(Challenge.created_at.desc()),
        per_page=PAGE_SIZE,
        max_per_page=PAGE_SIZE,
    )
    return render_template("admin/home.html", page=page, status_labels=STATUS_LABELS)


@bp.get("/challenges/<slug>")
@login_required
def challenge(slug: str):
    abort(404)
