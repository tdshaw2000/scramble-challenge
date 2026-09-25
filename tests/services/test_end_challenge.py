import pytest

from app import services
from app.models import ChallengeStatus


def finish(player, time_ms):
    services.start_inspection(player)
    services.start_solve(player)
    return services.stop_solve(player, time_ms=time_ms)


def test_co_ends_the_challenge_from_the_round_results(challenge, co):
    services.start_round(challenge, co)
    finish(co, 10_000)

    services.end_challenge(challenge, co)

    assert challenge.status == ChallengeStatus.ENDED


def test_only_the_co_can_end_the_challenge(challenge, co, add_player):
    guest = add_player("Guest")
    services.start_round(challenge, co)
    services.end_round(challenge, co)

    with pytest.raises(services.NotAllowed):
        services.end_challenge(challenge, guest)
    assert challenge.status == ChallengeStatus.ROUND_RESULTS


def test_cannot_end_the_challenge_before_any_round_has_finished(challenge, co):
    with pytest.raises(services.InvalidState):
        services.end_challenge(challenge, co)
    assert challenge.status == ChallengeStatus.WAITING


def test_cannot_end_the_challenge_while_a_round_is_running(challenge, co):
    services.start_round(challenge, co)

    with pytest.raises(services.InvalidState):
        services.end_challenge(challenge, co)
    assert challenge.status == ChallengeStatus.ROUND_ACTIVE


def test_cannot_end_a_challenge_twice(challenge, co):
    services.start_round(challenge, co)
    services.end_round(challenge, co)
    services.end_challenge(challenge, co)

    with pytest.raises(services.InvalidState):
        services.end_challenge(challenge, co)
