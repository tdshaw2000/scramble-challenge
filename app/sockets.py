"""Socket.IO handlers for the SPEC.md event contract. Kept thin: look up who is asking,
call services, and emit. One room per challenge, named by its slug."""

import functools
import uuid

from flask import request, url_for
from flask_socketio import emit, join_room

from app import game, services
from app.extensions import db, socketio
from app.models import Challenge, ChallengeStatus, Player, Round, RoundStatus
from app.routes import COOKIE_NAME

# Which player each open connection belongs to. In memory, so the app runs one worker.
connections: dict[str, str] = {}


def player_list(challenge: Challenge) -> list[dict]:
    points = services.points(challenge)
    return [
        {
            "player_id": str(p.id),
            "display_name": p.display_name,
            "is_co": p.is_co,
            "connected": p.connected,
            "points": points[p.id],
        }
        for p in challenge.players
    ]


def round_started(rnd: Round) -> dict:
    return {
        "round_id": str(rnd.id),
        "round_number": rnd.round_number,
        "puzzle": rnd.puzzle,
        "puzzle_name": game.PUZZLE_NAMES[rnd.puzzle],
        "scramble_text": rnd.scramble_text,
        "scramble_svg_url": url_for(
            "main.scramble_svg", slug=rnd.challenge.slug, round_number=rnd.round_number
        ),
    }


def round_results(rnd: Round) -> dict:
    return {"round_id": str(rnd.id), "results": services.leaderboard(rnd)}


def game_error(message: str) -> None:
    emit("game_error", {"message": message})


@socketio.on("join_challenge")
def on_join_challenge(data):
    challenge = services.get_challenge((data or {}).get("challenge_slug", ""))
    if challenge is None:
        return game_error("Challenge not found.")
    # Identity comes from the browser's own cookie, never from the payload.
    player = services.player_for_cookie(challenge, request.cookies.get(COOKIE_NAME))
    if player is None:
        return game_error("Enter your name to join first.")
    if challenge.status == ChallengeStatus.ENDED:
        # However it ended, the page reloads and the server sends it to the summary.
        return emit("challenge_ended", {})

    services.player_joined(player)
    join_room(challenge.slug)
    connections[request.sid] = str(player.id)
    emit("player_list", player_list(challenge), to=challenge.slug)

    if challenge.status == ChallengeStatus.ROUND_ACTIVE:
        emit("round_started", round_started(challenge.current_round))
    elif challenge.status == ChallengeStatus.ROUND_RESULTS:
        emit("round_complete", round_results(challenge.current_round))


def current_player() -> Player | None:
    player_id = connections.get(request.sid)
    return db.session.get(Player, uuid.UUID(player_id)) if player_id else None


def player_action(handler):
    """Run handler(player, data) for a joined player; report game errors to the sender."""

    @functools.wraps(handler)
    def wrapper(data=None):
        player = current_player()
        if player is None:
            return game_error("Join the challenge first.")
        try:
            handler(player, data or {})
        except services.GameError as error:
            db.session.rollback()
            game_error(str(error))

    return wrapper


def broadcast_round_complete(challenge: Challenge, rnd: Round) -> None:
    emit("round_complete", round_results(rnd), to=challenge.slug)
    # The winners' points just went up, and the players list shows them.
    emit("player_list", player_list(challenge), to=challenge.slug)


def broadcast_solve_progress(challenge: Challenge, rnd: Round) -> None:
    emit("leaderboard_update", round_results(rnd), to=challenge.slug)
    if rnd.status == RoundStatus.COMPLETE:
        broadcast_round_complete(challenge, rnd)


@socketio.on("start_round")
@player_action
def on_start_round(player, data):
    rnd = services.start_round(player.challenge, player, puzzle=data.get("puzzle"))
    emit("round_started", round_started(rnd), to=rnd.challenge.slug)


@socketio.on("start_inspection")
@player_action
def on_start_inspection(player, data):
    services.start_inspection(player)


@socketio.on("start_solve")
@player_action
def on_start_solve(player, data):
    services.start_solve(player)


@socketio.on("inspection_expired")
@player_action
def on_inspection_expired(player, data):
    solve = services.inspection_expired(player)
    broadcast_solve_progress(player.challenge, solve.round)


@socketio.on("stop_solve")
@player_action
def on_stop_solve(player, data):
    solve = services.stop_solve(player, time_ms=data.get("time_ms"))
    broadcast_solve_progress(player.challenge, solve.round)


@socketio.on("end_round")
@player_action
def on_end_round(player, data):
    rnd = services.end_round(player.challenge, player)
    broadcast_round_complete(rnd.challenge, rnd)


@socketio.on("disconnect")
def on_disconnect(*_reason):
    player_id = connections.pop(request.sid, None)
    if player_id is None or player_id in connections.values():
        return  # never joined, or the player still has another tab open
    player = db.session.get(Player, uuid.UUID(player_id))
    challenge = player.challenge
    round_was_active = challenge.status == ChallengeStatus.ROUND_ACTIVE
    services.player_left(player)
    emit("player_list", player_list(challenge), to=challenge.slug)
    if round_was_active:
        broadcast_solve_progress(challenge, challenge.current_round)


def end_abandoned_challenges() -> None:
    for challenge in services.end_abandoned_challenges():
        socketio.emit("challenge_ended", {}, to=challenge.slug)


def watch_for_abandoned_challenges(app, interval_seconds: int = 5) -> None:  # pragma: no cover
    """Background loop, started by app/wsgi.py in production. Deliberately untested: an
    endless loop around end_abandoned_challenges(), which the tests cover directly."""
    while True:
        socketio.sleep(interval_seconds)
        with app.app_context():
            end_abandoned_challenges()
