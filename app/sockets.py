"""Socket.IO handlers for the SPEC.md event contract. Kept thin: look up who is asking,
call services, and emit. One room per challenge, named by its slug."""

from flask import request, url_for
from flask_socketio import emit, join_room

from app import services
from app.extensions import socketio
from app.models import Challenge, ChallengeStatus, Round
from app.routes import COOKIE_NAME

# Which player each open connection belongs to. In memory, so the app runs one worker.
connections: dict[str, str] = {}


def player_list(challenge: Challenge) -> list[dict]:
    return [
        {
            "player_id": str(p.id),
            "display_name": p.display_name,
            "is_co": p.is_co,
            "connected": p.connected,
        }
        for p in challenge.players
    ]


def round_started(rnd: Round) -> dict:
    return {
        "round_id": str(rnd.id),
        "round_number": rnd.round_number,
        "puzzle": rnd.puzzle,
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

    join_room(challenge.slug)
    connections[request.sid] = str(player.id)
    services.set_connected(player, True)
    emit("player_list", player_list(challenge), to=challenge.slug)

    if challenge.status == ChallengeStatus.ROUND_ACTIVE:
        emit("round_started", round_started(challenge.current_round))
    elif challenge.status == ChallengeStatus.ROUND_RESULTS:
        emit("round_complete", round_results(challenge.current_round))
