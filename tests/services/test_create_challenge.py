import pytest

from app import services
from app.models import ChallengeStatus


def test_create_challenge_makes_a_waiting_challenge_owned_by_its_creator(db, clock):
    challenge = services.create_challenge(display_name="Tom", cookie_id="cookie-1")

    assert challenge.status == ChallengeStatus.WAITING
    assert challenge.co_player.display_name == "Tom"
    assert challenge.co_player.cookie_id == "cookie-1"
    assert challenge.co_player.is_co is True
    assert challenge.players == [challenge.co_player]
    assert challenge.created_at == clock.now.replace(tzinfo=None)


def test_challenge_slugs_are_short_url_safe_and_unique(db):
    slugs = {services.create_challenge("Tom", f"c{i}").slug for i in range(50)}

    assert len(slugs) == 50
    for slug in slugs:
        assert 6 <= len(slug) <= 12
        assert slug.isascii() and all(c.isalnum() or c in "-_" for c in slug)


def test_display_name_is_trimmed(db):
    challenge = services.create_challenge("  Tom  ", "cookie-1")

    assert challenge.co_player.display_name == "Tom"


@pytest.mark.parametrize("name", ["", "   ", "x" * 51])
def test_blank_or_overlong_names_are_rejected(db, name):
    with pytest.raises(services.InvalidInput):
        services.create_challenge(name, "cookie-1")


def test_challenge_can_be_found_by_slug(db):
    challenge = services.create_challenge("Tom", "cookie-1")

    assert services.get_challenge(challenge.slug) == challenge
    assert services.get_challenge("missing") is None
