import pytest

from app import services
from app.models import ChallengeStatus, RoundStatus


def test_co_starts_round_one_with_a_fresh_scramble(challenge, co, tnoodle, clock):
    rnd = services.start_round(challenge, co)

    assert rnd.round_number == 1
    assert rnd.puzzle == "333"
    assert rnd.scramble_text == "R U R' U' 1"
    assert rnd.scramble_svg == "<svg>333 1</svg>"
    assert rnd.status == RoundStatus.ACTIVE
    assert rnd.started_at == clock.now.replace(tzinfo=None)
    assert tnoodle.requested == ["333"]
    assert challenge.status == ChallengeStatus.ROUND_ACTIVE
    assert challenge.current_round == rnd


def test_only_the_co_can_start_a_round(challenge, add_player):
    guest = add_player("Guest")

    with pytest.raises(services.NotAllowed):
        services.start_round(challenge, guest)


def test_cannot_start_a_round_while_one_is_active(challenge, co):
    services.start_round(challenge, co)

    with pytest.raises(services.InvalidState):
        services.start_round(challenge, co)


def test_next_round_can_start_from_results_and_is_numbered_on(challenge, co):
    services.start_round(challenge, co)
    services.end_round(challenge, co)

    second = services.start_round(challenge, co)

    assert second.round_number == 2
    assert challenge.current_round == second


def test_later_rounds_default_to_the_previous_puzzle(challenge, co, monkeypatch):
    monkeypatch.setattr(services, "SUPPORTED_PUZZLES", ("333", "222"))
    services.start_round(challenge, co, puzzle="222")
    services.end_round(challenge, co)

    assert services.next_puzzle_default(challenge) == "222"
    assert services.start_round(challenge, co).puzzle == "222"


def test_first_round_default_is_3x3(challenge):
    assert services.next_puzzle_default(challenge) == "333"


def test_unsupported_puzzle_is_rejected_without_calling_tnoodle(challenge, co, tnoodle):
    with pytest.raises(services.InvalidInput):
        services.start_round(challenge, co, puzzle="minx")

    assert tnoodle.requested == []
    assert challenge.status == ChallengeStatus.WAITING


def test_tnoodle_failure_leaves_the_challenge_waiting(challenge, co, tnoodle):
    tnoodle.fail = True

    with pytest.raises(services.ScrambleUnavailable):
        services.start_round(challenge, co)

    assert challenge.status == ChallengeStatus.WAITING
    assert challenge.rounds == []
