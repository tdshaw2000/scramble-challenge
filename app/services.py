"""Game operations on the database. Handlers (HTTP now, sockets later) call these."""

import secrets
from dataclasses import dataclass
from datetime import datetime

from flask import current_app

from app import game
from app.extensions import db
from app.models import Challenge, ChallengeStatus, Player, Round, RoundStatus, Solve, SolveResult
from app.tnoodle import TNoodleError

MAX_NAME_LENGTH = 50

# v1 offers 3x3 only; more WCA events are a change to this list, not the schema.
SUPPORTED_PUZZLES = ("333",)


class GameError(Exception):
    pass


class InvalidInput(GameError):
    pass


class NotAllowed(GameError):
    pass


class InvalidState(GameError):
    pass


class ScrambleUnavailable(GameError):
    pass


def now() -> datetime:
    return current_app.extensions["clock"]()


def clean_display_name(display_name: str) -> str:
    name = display_name.strip()
    if not name or len(name) > MAX_NAME_LENGTH:
        raise InvalidInput(f"Name must be 1 to {MAX_NAME_LENGTH} characters.")
    return name


def new_slug() -> str:
    while True:
        slug = secrets.token_urlsafe(6)  # 8 url-safe characters
        if get_challenge(slug) is None:
            return slug


def create_challenge(display_name: str, cookie_id: str) -> Challenge:
    name = clean_display_name(display_name)
    timestamp = now()
    challenge = Challenge(slug=new_slug(), created_at=timestamp)
    co = Player(
        challenge=challenge,
        cookie_id=cookie_id,
        display_name=name,
        is_co=True,
        joined_at=timestamp,
    )
    challenge.co_player = co
    db.session.add(challenge)
    db.session.commit()
    return challenge


def get_challenge(slug: str) -> Challenge | None:
    return db.session.scalar(db.select(Challenge).filter_by(slug=slug))


def require_co(challenge: Challenge, player: Player) -> None:
    if player.id != challenge.co_player_id:
        raise NotAllowed("Only the challenge owner can do that.")


def next_puzzle_default(challenge: Challenge) -> str:
    previous = challenge.rounds[-1].puzzle if challenge.rounds else None
    return game.default_puzzle(previous)


def start_round(challenge: Challenge, player: Player, puzzle: str | None = None) -> Round:
    require_co(challenge, player)
    if challenge.status not in (ChallengeStatus.WAITING, ChallengeStatus.ROUND_RESULTS):
        raise InvalidState("A round is already in progress.")
    puzzle = puzzle or next_puzzle_default(challenge)
    if puzzle not in SUPPORTED_PUZZLES:
        raise InvalidInput(f"Unsupported puzzle: {puzzle}")

    try:
        scramble = current_app.extensions["tnoodle"].generate(puzzle)
    except TNoodleError as error:
        raise ScrambleUnavailable("Couldn't get a scramble; try again.") from error

    rnd = Round(
        challenge=challenge,
        round_number=len(challenge.rounds) + 1,
        puzzle=puzzle,
        scramble_text=scramble.text,
        scramble_svg=scramble.svg,
        started_at=now(),
    )
    challenge.status = ChallengeStatus.ROUND_ACTIVE
    challenge.current_round = rnd
    db.session.commit()
    return rnd


def active_round(player: Player) -> Round:
    challenge = player.challenge
    if challenge.status != ChallengeStatus.ROUND_ACTIVE:
        raise InvalidState("No round is in progress.")
    return challenge.current_round


def find_solve(rnd: Round, player: Player) -> Solve | None:
    return db.session.scalar(db.select(Solve).filter_by(round_id=rnd.id, player_id=player.id))


def start_inspection(player: Player) -> Solve:
    rnd = active_round(player)
    if find_solve(rnd, player) is not None:
        raise InvalidState("One attempt per round.")
    solve = Solve(round=rnd, player=player, started_inspection_at=now())
    db.session.add(solve)
    db.session.commit()
    return solve


def start_solve(player: Player) -> Solve:
    solve = find_solve(active_round(player), player)
    if solve is None or solve.started_solve_at is not None:
        raise InvalidState("Start inspection first, and only start solving once.")
    solve.started_solve_at = now()
    db.session.commit()
    return solve


def stop_solve(player: Player, time_ms: int) -> Solve:
    # Trust boundary: time_ms comes from the client (honour system, per SPEC.md).
    # To enforce timing, compute it here from started_solve_at and now() instead.
    if type(time_ms) is not int or time_ms <= 0:
        raise InvalidInput("time_ms must be a positive whole number.")
    solve = find_solve(active_round(player), player)
    if solve is None or solve.started_solve_at is None or solve.result is not None:
        raise InvalidState("No solve in progress.")
    solve.time_ms = time_ms
    solve.result = SolveResult.OK
    solve.finished_at = now()
    db.session.commit()
    complete_round_if_everyone_finished(player.challenge)
    return solve


def end_round(challenge: Challenge, player: Player) -> Round:
    require_co(challenge, player)
    if challenge.status != ChallengeStatus.ROUND_ACTIVE:
        raise InvalidState("No round is in progress.")
    return complete_round(challenge)


def complete_round(challenge: Challenge) -> Round:
    """Close the current round: every connected player without a result gets a DNF."""
    rnd = challenge.current_round
    solves = {solve.player_id: solve for solve in rnd.solves}
    for player in challenge.players:
        solve = solves.get(player.id)
        if solve is None and player.connected:
            solve = Solve(round=rnd, player=player)
            db.session.add(solve)
        if solve is not None and solve.result is None:
            solve.result = SolveResult.DNF
            solve.time_ms = None
    rnd.status = RoundStatus.COMPLETE
    rnd.ended_at = now()
    challenge.status = ChallengeStatus.ROUND_RESULTS
    db.session.commit()
    return rnd


def complete_round_if_everyone_finished(challenge: Challenge) -> None:
    rnd = challenge.current_round
    connected = {p.id for p in challenge.players if p.connected}
    finished = {s.player_id for s in rnd.solves if s.result is not None}
    if game.round_is_over(connected=connected, finished=finished):
        complete_round(challenge)


@dataclass
class _Row:
    name: str
    time_ms: int | None
    solve: Solve


def leaderboard(rnd: Round) -> list[dict]:
    rows = [
        _Row(name=s.player.display_name, time_ms=s.time_ms, solve=s)
        for s in rnd.solves
        if s.result is not None
    ]
    return [
        {
            "player_id": str(row.solve.player_id),
            "display_name": row.name,
            "time_ms": row.time_ms,
            "result": row.solve.result.value,
            "position": position,
        }
        for position, row in game.rank(rows)
    ]


def player_for_cookie(challenge: Challenge, cookie_id: str | None) -> Player | None:
    if not cookie_id:
        return None
    return db.session.scalar(
        db.select(Player).filter_by(challenge_id=challenge.id, cookie_id=cookie_id)
    )


def join_challenge(challenge: Challenge, display_name: str, cookie_id: str) -> Player:
    existing = player_for_cookie(challenge, cookie_id)
    if existing is not None:
        return existing
    player = Player(
        challenge=challenge,
        cookie_id=cookie_id,
        display_name=clean_display_name(display_name),
        joined_at=now(),
    )
    db.session.add(player)
    db.session.commit()
    return player


def set_connected(player: Player, connected: bool) -> None:
    player.connected = connected
    db.session.commit()
