import secrets
from urllib.parse import urlsplit

from flask import (
    Blueprint,
    Response,
    abort,
    current_app,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from sqlalchemy import text

from app import game, services
from app.extensions import db
from app.models import ChallengeStatus, Round

bp = Blueprint("main", __name__)

COOKIE_NAME = "scramble_device"
COOKIE_MAX_AGE = 60 * 60 * 24 * 365
NAME_COOKIE_NAME = "scramble_name"
SKIN_COOKIE_NAME = "scramble_skin"


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


def with_name_cookie(response, display_name: str):
    response.set_cookie(
        NAME_COOKIE_NAME, display_name, max_age=COOKIE_MAX_AGE, httponly=True, samesite="Lax"
    )
    return response


@bp.context_processor
def remembered_name():
    name = request.cookies.get(NAME_COOKIE_NAME, "")
    return {"remembered_name": name[: services.MAX_NAME_LENGTH]}


@bp.app_context_processor
def chosen_skin():
    """The player's own skin if they picked one, otherwise the server's THEME."""
    skins = current_app.config["THEMES"]
    skin = request.cookies.get(SKIN_COOKIE_NAME)
    if skin not in skins:
        skin = current_app.config["THEME"]
    return {"skin": skin, "skins": skins, "skin_next": skin_return_path()}


def skin_return_path() -> str:
    """Where the skin menu goes back to. A page drawn after a failed form (a POST) has no
    GET of its own, so go back to the page the form was on, or home."""
    if request.method == "GET":
        return request.full_path.rstrip("?")
    referrer = urlsplit(request.referrer or "")
    if referrer.netloc == request.host and is_local_path(referrer.path):
        return referrer.path
    return "/"


def is_local_path(url: str) -> bool:
    """A path on this site. Whitespace, control characters and backslashes are refused
    because browsers drop or rewrite them, which can turn "/<tab>/x" into "//x"."""
    if any(c.isspace() or not c.isprintable() or c == "\\" for c in url):
        return False
    return url.startswith("/") and not url.startswith("//")


@bp.post("/skin")
def choose_skin():
    skin = request.form.get("skin", "")
    if skin not in current_app.config["THEMES"]:
        abort(400)
    next_url = request.form.get("next", "")
    response = redirect(next_url if is_local_path(next_url) else "/", code=303)
    response.set_cookie(
        SKIN_COOKIE_NAME, skin, max_age=COOKIE_MAX_AGE, httponly=True, samesite="Lax"
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
    with_name_cookie(response, challenge.co_player.display_name)
    return with_device_cookie(response, cookie_id)


@bp.get("/c/<slug>")
def challenge(slug: str):
    challenge = challenge_or_404(slug)
    if challenge.status == ChallengeStatus.ENDED:
        return redirect(url_for("main.summary", slug=slug))
    player = services.player_for_cookie(challenge, request.cookies.get(COOKIE_NAME))
    if player is None:
        return render_template("join.html", challenge=challenge)
    return render_template(
        "challenge.html",
        challenge=challenge,
        player=player,
        points=services.points(challenge),
        share_url=url_for("main.challenge", slug=slug, _external=True),
        puzzles={code: game.PUZZLE_NAMES[code] for code in services.SUPPORTED_PUZZLES},
        default_puzzle=services.next_puzzle_default(challenge),
    )


@bp.post("/c/<slug>/join")
def join(slug: str):
    challenge = challenge_or_404(slug)
    if challenge.status == ChallengeStatus.ENDED:
        return redirect(url_for("main.summary", slug=slug))
    cookie_id = device_cookie()
    try:
        player = services.join_challenge(challenge, request.form.get("display_name", ""), cookie_id)
    except services.InvalidInput as error:
        return render_template("join.html", challenge=challenge, error=str(error)), 400
    response = redirect(url_for("main.challenge", slug=slug))
    with_name_cookie(response, player.display_name)
    return with_device_cookie(response, cookie_id)


@bp.get("/c/<slug>/summary")
def summary(slug: str):
    """What happened in an ended challenge. Anyone with the link can see it."""
    challenge = challenge_or_404(slug)
    if challenge.status != ChallengeStatus.ENDED:
        return redirect(url_for("main.challenge", slug=slug))
    return render_template(
        "summary.html",
        challenge=challenge,
        standings=services.standings(challenge),
        puzzle_names=game.PUZZLE_NAMES,
        leaderboards={rnd.id: services.leaderboard(rnd) for rnd in challenge.rounds},
    )


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
