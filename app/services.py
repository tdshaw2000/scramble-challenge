"""Game operations on the database. Handlers (HTTP now, sockets later) call these."""

import secrets
from datetime import datetime

from flask import current_app

from app.extensions import db
from app.models import Challenge, Player

MAX_NAME_LENGTH = 50


class GameError(Exception):
    pass


class InvalidInput(GameError):
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
