import pytest

from app import services


def test_joining_adds_a_non_co_player(challenge, clock):
    player = services.join_challenge(challenge, "  Amy ", "cookie-amy")

    assert player.display_name == "Amy"
    assert player.is_co is False
    assert player.challenge == challenge
    assert player.joined_at == clock.now.replace(tzinfo=None)


def test_joining_again_with_the_same_cookie_returns_the_existing_player(challenge):
    first = services.join_challenge(challenge, "Amy", "cookie-amy")

    again = services.join_challenge(challenge, "Amelia", "cookie-amy")

    assert again == first
    assert again.display_name == "Amy"
    assert len(challenge.players) == 2


def test_join_rejects_a_blank_name(challenge):
    with pytest.raises(services.InvalidInput):
        services.join_challenge(challenge, " ", "cookie-amy")


def test_player_for_cookie(challenge, co):
    assert services.player_for_cookie(challenge, "cookie-co") == co
    assert services.player_for_cookie(challenge, "stranger") is None
    assert services.player_for_cookie(challenge, None) is None
