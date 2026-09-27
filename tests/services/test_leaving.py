from datetime import timedelta

import pytest

from app import services
from app.models import ChallengeStatus, RoundStatus, SolveResult


def result_of(rnd, player):
    return next((s.result for s in rnd.solves if s.player == player), "no solve")


def test_leaving_outside_a_round_just_marks_the_player_disconnected(challenge, add_player):
    amy = add_player("Amy")

    services.player_left(amy)

    assert amy.connected is False


def test_leaving_mid_round_without_a_result_is_a_dnf(challenge, co, add_player):
    amy, bob = add_player("Amy"), add_player("Bob")
    rnd = services.start_round(challenge, co)
    services.start_inspection(amy)

    services.player_left(amy)
    services.player_left(bob)

    assert result_of(rnd, amy) == SolveResult.DNF
    assert result_of(rnd, bob) == SolveResult.DNF
    assert rnd.status == RoundStatus.ACTIVE  # Tom is still solving


def test_leaving_after_finishing_keeps_the_time(challenge, co, add_player):
    amy = add_player("Amy")
    rnd = services.start_round(challenge, co)
    services.start_inspection(amy)
    services.start_solve(amy)
    services.stop_solve(amy, time_ms=8_000)

    services.player_left(amy)

    assert result_of(rnd, amy) == SolveResult.OK


def test_the_last_unfinished_player_leaving_completes_the_round(challenge, co, add_player):
    amy = add_player("Amy")
    rnd = services.start_round(challenge, co)
    services.start_inspection(co)
    services.start_solve(co)
    services.stop_solve(co, time_ms=8_000)

    services.player_left(amy)

    assert rnd.status == RoundStatus.COMPLETE


def test_co_leaving_starts_the_grace_period_and_rejoining_cancels_it(challenge, co, clock):
    services.player_left(co)
    assert challenge.co_left_at == clock.now.replace(tzinfo=None)

    services.player_joined(co)

    assert challenge.co_left_at is None
    assert co.connected is True


def test_challenge_ends_once_the_co_has_been_gone_past_the_grace_period(app, challenge, co, clock):
    grace = app.config["CO_GRACE_SECONDS"]
    services.player_left(co)

    clock.advance(seconds=grace - 1)
    assert services.end_abandoned_challenges() == []

    clock.advance(seconds=1)
    assert services.end_abandoned_challenges() == [challenge]
    assert challenge.status == ChallengeStatus.ENDED
    assert services.end_abandoned_challenges() == []


def test_co_back_within_the_grace_period_keeps_the_challenge(app, challenge, co, clock):
    services.player_left(co)
    clock.advance(seconds=app.config["CO_GRACE_SECONDS"] - 1)
    services.player_joined(co)

    clock.advance(seconds=60)

    assert services.end_abandoned_challenges() == []
    assert challenge.status == ChallengeStatus.WAITING


def test_grace_period_is_short(app):
    assert timedelta(seconds=app.config["CO_GRACE_SECONDS"]) == timedelta(seconds=30)


def test_an_ended_challenge_cannot_start_rounds_or_be_joined(challenge, co, clock, app):
    services.player_left(co)
    clock.advance(seconds=app.config["CO_GRACE_SECONDS"])
    services.end_abandoned_challenges()

    with pytest.raises(services.InvalidState, match="has ended"):
        services.player_joined(co)
    with pytest.raises(services.InvalidState, match="has ended"):
        services.start_round(challenge, co)


def test_an_active_round_is_closed_when_the_challenge_ends(challenge, co, add_player, clock, app):
    add_player("Amy")
    rnd = services.start_round(challenge, co)
    services.player_left(co)
    clock.advance(seconds=app.config["CO_GRACE_SECONDS"])

    services.end_abandoned_challenges()

    assert rnd.status == RoundStatus.COMPLETE
    assert challenge.status == ChallengeStatus.ENDED


def test_leaving_after_a_late_start_is_a_plain_dnf(challenge, co, add_player):
    amy, _bob = add_player("Amy"), add_player("Bob")
    rnd = services.start_round(challenge, co)
    services.start_inspection(amy)
    services.start_solve(amy, plus_two=True)

    services.player_left(amy)

    [solve] = [s for s in rnd.solves if s.player == amy]
    assert (solve.result, solve.plus_two) == (SolveResult.DNF, False)
