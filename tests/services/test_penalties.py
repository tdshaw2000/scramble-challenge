"""A player can mark their own finished solve as +2 or DNF, and undo it, until the next round
starts. Both are toggles: the timed solve is kept, so turning a penalty off brings it back."""

import pytest

from app import services
from app.models import ChallengeStatus, SolveResult


def finish(player, time_ms, plus_two=False):
    services.start_inspection(player)
    services.start_solve(player, plus_two=plus_two)
    return services.stop_solve(player, time_ms=time_ms)


def row(rnd, name):
    return next(r for r in services.leaderboard(rnd) if r["display_name"] == name)


@pytest.fixture
def amy(add_player):
    return add_player("Amy")


@pytest.fixture
def rnd(challenge, co, amy):
    return services.start_round(challenge, co)


def test_a_player_can_add_a_plus_two_while_others_are_still_solving(rnd, co):
    finish(co, 12_340)

    solve = services.set_penalty(co, plus_two=True, dnf=False)

    assert solve.plus_two is True
    assert solve.result == SolveResult.OK
    assert solve.time_ms == 12_340  # the timed solve is kept; the +2 is added when it counts
    assert row(rnd, "Tom")["time_ms"] == 14_340


def test_a_plus_two_can_be_turned_off_again(rnd, co):
    finish(co, 12_340)
    services.set_penalty(co, plus_two=True, dnf=False)

    solve = services.set_penalty(co, plus_two=False, dnf=False)

    assert solve.plus_two is False
    assert row(rnd, "Tom")["time_ms"] == 12_340


def test_a_plus_two_from_inspection_can_be_turned_off(rnd, co):
    finish(co, 12_340, plus_two=True)

    services.set_penalty(co, plus_two=False, dnf=False)

    assert row(rnd, "Tom")["plus_two"] is False
    assert row(rnd, "Tom")["time_ms"] == 12_340


def test_a_dnf_keeps_the_timed_solve_but_counts_as_a_dnf(rnd, co):
    finish(co, 12_340)

    solve = services.set_penalty(co, plus_two=False, dnf=True)

    assert solve.result == SolveResult.DNF
    assert solve.time_ms == 12_340
    tom = row(rnd, "Tom")
    assert tom["result"] == "dnf"
    assert tom["time_ms"] is None


def test_turning_a_dnf_off_brings_back_the_time_and_any_plus_two(rnd, co):
    finish(co, 12_340, plus_two=True)
    services.set_penalty(co, plus_two=True, dnf=True)

    solve = services.set_penalty(co, plus_two=True, dnf=False)

    assert solve.result == SolveResult.OK
    tom = row(rnd, "Tom")
    assert tom["result"] == "ok"
    assert tom["time_ms"] == 14_340
    assert tom["plus_two"] is True


def test_a_dnf_ranks_last_even_though_its_time_is_kept(challenge, rnd, co, amy):
    finish(co, 9_000)
    finish(amy, 12_000)

    services.set_penalty(co, plus_two=False, dnf=True)

    board = services.leaderboard(rnd)
    assert [(r["display_name"], r["position"]) for r in board] == [("Amy", 1), ("Tom", 2)]


def test_a_dnf_loses_the_round_win_point(challenge, rnd, co, amy):
    finish(co, 9_000)
    finish(amy, 12_000)
    assert services.points(challenge)[co.id] == 1

    services.set_penalty(co, plus_two=False, dnf=True)

    assert services.points(challenge)[co.id] == 0
    assert services.points(challenge)[amy.id] == 1


def test_a_plus_two_can_hand_the_round_win_to_someone_else(challenge, rnd, co, amy):
    finish(co, 9_000)
    finish(amy, 10_000)

    services.set_penalty(co, plus_two=True, dnf=False)

    assert services.points(challenge)[co.id] == 0
    assert services.points(challenge)[amy.id] == 1


def test_penalties_can_be_changed_while_the_round_results_show(challenge, rnd, co, amy):
    finish(co, 9_000)
    finish(amy, 10_000)
    assert challenge.status == ChallengeStatus.ROUND_RESULTS

    services.set_penalty(amy, plus_two=False, dnf=True)

    assert row(rnd, "Amy")["result"] == "dnf"


def test_a_round_is_locked_once_the_next_round_starts(challenge, rnd, co, amy):
    finish(co, 9_000)
    finish(amy, 10_000)
    services.start_round(challenge, co)

    with pytest.raises(services.InvalidState):
        services.set_penalty(co, plus_two=True, dnf=False)
    assert row(rnd, "Tom")["plus_two"] is False


def test_nothing_can_be_changed_once_the_challenge_has_ended(challenge, rnd, co, amy):
    finish(co, 9_000)
    finish(amy, 10_000)
    services.end_challenge(challenge, co)

    with pytest.raises(services.InvalidState):
        services.set_penalty(co, plus_two=False, dnf=True)
    assert row(rnd, "Tom")["result"] == "ok"


def test_nothing_can_be_changed_before_the_first_round(challenge, co):
    with pytest.raises(services.InvalidState):
        services.set_penalty(co, plus_two=True, dnf=False)


def test_a_solve_still_in_progress_cannot_be_changed(rnd, co):
    services.start_inspection(co)
    services.start_solve(co)

    with pytest.raises(services.InvalidState):
        services.set_penalty(co, plus_two=True, dnf=False)


def test_a_player_without_a_solve_cannot_change_anything(rnd, co):
    with pytest.raises(services.InvalidState):
        services.set_penalty(co, plus_two=True, dnf=False)


def test_a_dnf_from_inspection_running_out_has_no_time_to_bring_back(rnd, co):
    services.start_inspection(co)
    services.inspection_expired(co)

    with pytest.raises(services.InvalidState):
        services.set_penalty(co, plus_two=False, dnf=False)
    assert row(rnd, "Tom")["result"] == "dnf"


def test_a_dnf_from_the_round_being_ended_has_no_time_to_bring_back(challenge, rnd, co):
    services.end_round(challenge, co)

    with pytest.raises(services.InvalidState):
        services.set_penalty(co, plus_two=False, dnf=False)


def test_a_dnf_from_leaving_has_no_time_to_bring_back(challenge, rnd, co, amy):
    services.player_left(amy)

    with pytest.raises(services.InvalidState):
        services.set_penalty(amy, plus_two=False, dnf=False)


@pytest.mark.parametrize("field", ["plus_two", "dnf"])
@pytest.mark.parametrize("bad", [None, 1, "true"])
def test_penalties_must_be_true_or_false(rnd, co, field, bad):
    finish(co, 9_000)
    choice = {"plus_two": False, "dnf": False, field: bad}

    with pytest.raises(services.InvalidInput):
        services.set_penalty(co, **choice)


def test_leaderboard_says_which_solves_have_a_time_that_can_be_penalised(rnd, co, amy):
    finish(co, 9_000)
    services.set_penalty(co, plus_two=False, dnf=True)
    services.start_inspection(amy)
    services.inspection_expired(amy)

    assert row(rnd, "Tom")["timed"] is True
    assert row(rnd, "Amy")["timed"] is False
