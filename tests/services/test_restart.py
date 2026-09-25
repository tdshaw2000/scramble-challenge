"""A restart (every deploy) kills the server without running any disconnect handlers, so
the database still says everyone is connected. Browsers reconnect by themselves within
seconds, so startup marks everyone as away and lets them rejoin."""

from app import services
from app.models import ChallengeStatus


def naive(dt):
    return dt.replace(tzinfo=None)


def test_after_a_restart_nobody_counts_as_connected_until_they_rejoin(challenge, co, add_player):
    amy = add_player("Amy")

    services.reset_presence_after_restart()

    assert (co.connected, amy.connected) == (False, False)
    services.player_joined(amy)
    assert amy.connected is True


def test_after_a_restart_the_owner_gets_the_usual_grace_period(app, challenge, co, clock):
    services.reset_presence_after_restart()

    assert challenge.co_left_at == naive(clock.now)
    clock.advance(seconds=app.config["CO_GRACE_SECONDS"])
    assert services.end_abandoned_challenges() == [challenge]


def test_an_owner_who_comes_back_after_a_restart_keeps_the_challenge(app, challenge, co, clock):
    services.reset_presence_after_restart()
    services.player_joined(co)

    clock.advance(seconds=app.config["CO_GRACE_SECONDS"] + 60)

    assert services.end_abandoned_challenges() == []
    assert challenge.status == ChallengeStatus.WAITING


def test_an_owner_already_away_keeps_their_original_leaving_time(challenge, co, clock):
    services.player_left(co)
    left_at = challenge.co_left_at
    clock.advance(seconds=10)

    services.reset_presence_after_restart()

    assert challenge.co_left_at == left_at


def test_a_restart_mid_round_does_not_cost_anyone_their_attempt(challenge, co, add_player):
    add_player("Amy")
    services.start_round(challenge, co)
    solve = services.start_inspection(co)

    services.reset_presence_after_restart()

    assert solve.result is None
    assert challenge.status == ChallengeStatus.ROUND_ACTIVE


def test_ended_challenges_are_left_alone(app, challenge, co, clock):
    services.player_left(co)
    clock.advance(seconds=app.config["CO_GRACE_SECONDS"])
    services.end_abandoned_challenges()
    ended_at = challenge.co_left_at
    clock.advance(seconds=5)

    services.reset_presence_after_restart()

    assert challenge.co_left_at == ended_at
