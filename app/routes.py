import secrets

from flask import (
    Blueprint,
    Response,
    abort,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from sqlalchemy import text

from app import game, services
from app.extensions import db
from app.models import Round

bp = Blueprint("main", __name__)

COOKIE_NAME = "scramble_device"
COOKIE_MAX_AGE = 60 * 60 * 24 * 365


@bp.get("/healthz")
def health():
    db.session.execute(text("SELECT 1"))
    return jsonify(status="ok")


def device_cookie() -> str:
    return request.cookies.get(COOKIE_NAME) or secrets.token_urlsafe(24)


def with_device_cookie(response, cookie_id: str):
    response.set_cookie(
        COOKIE_NAME, cookie_id, max_age=COOKIE_MAX_AGE, httponly=True, samesite="Lax"
    )
    return response


def challenge_or_404(slug: str):
    challenge = services.get_challenge(slug)
    if challenge is None:
        abort(404)
    return challenge


@bp.get("/")
def landing():
    return render_template("landing.html")


@bp.post("/challenges")
def create_challenge():
    cookie_id = device_cookie()
    try:
        challenge = services.create_challenge(request.form.get("display_name", ""), cookie_id)
    except services.InvalidInput as error:
        return render_template("landing.html", error=str(error)), 400
    response = redirect(url_for("main.challenge", slug=challenge.slug))
    return with_device_cookie(response, cookie_id)


@bp.get("/c/<slug>")
def challenge(slug: str):
    challenge = challenge_or_404(slug)
    player = services.player_for_cookie(challenge, request.cookies.get(COOKIE_NAME))
    if player is None:
        return render_template("join.html", challenge=challenge)
    return render_template(
        "challenge.html",
        challenge=challenge,
        player=player,
        share_url=url_for("main.challenge", slug=slug, _external=True),
        puzzles={code: game.PUZZLE_NAMES[code] for code in services.SUPPORTED_PUZZLES},
        default_puzzle=services.next_puzzle_default(challenge),
    )


@bp.post("/c/<slug>/join")
def join(slug: str):
    challenge = challenge_or_404(slug)
    cookie_id = device_cookie()
    try:
        services.join_challenge(challenge, request.form.get("display_name", ""), cookie_id)
    except services.InvalidInput as error:
        return render_template("join.html", challenge=challenge, error=str(error)), 400
    response = redirect(url_for("main.challenge", slug=slug))
    return with_device_cookie(response, cookie_id)


@bp.get("/c/<slug>/rounds/<int:round_number>/scramble.svg")
def scramble_svg(slug: str, round_number: int):
    challenge = challenge_or_404(slug)
    rnd = db.session.scalar(
        db.select(Round).filter_by(challenge_id=challenge.id, round_number=round_number)
    )
    if rnd is None:
        abort(404)
    response = Response(rnd.scramble_svg, mimetype="image/svg+xml")
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response
