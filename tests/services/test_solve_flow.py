import pytest

from app import services
from app.models import SolveResult


def naive(dt):
    return dt.replace(tzinfo=None)


@pytest.fixture
def rnd(challenge, co, add_player):
    # A second connected player keeps the round open after the CO finishes.
    add_player("Other")
    return services.start_round(challenge, co)


def test_start_inspection_creates_the_players_solve(rnd, co, clock):
    solve = services.start_inspection(co)

    assert solve.round == rnd
    assert solve.player == co
    assert solve.started_inspection_at == naive(clock.now)
    assert solve.result is None


def test_full_solve_records_time_and_timestamps(rnd, co, clock):
    services.start_inspection(co)
    clock.advance(seconds=8)
    services.start_solve(co)
    started = clock.now
    clock.advance(seconds=12)

    solve = services.stop_solve(co, time_ms=11_987)

    assert solve.time_ms == 11_987
    assert solve.result == SolveResult.OK
    assert solve.started_solve_at == naive(started)
    assert solve.finished_at == naive(clock.now)


def test_one_attempt_per_round(rnd, co):
    services.start_inspection(co)

    with pytest.raises(services.InvalidState):
        services.start_inspection(co)


def test_cannot_start_inspection_without_an_active_round(challenge, co):
    with pytest.raises(services.InvalidState):
        services.start_inspection(co)


def test_cannot_start_solving_before_inspection(rnd, co):
    with pytest.raises(services.InvalidState):
        services.start_solve(co)


def test_cannot_start_solving_twice(rnd, co):
    services.start_inspection(co)
    services.start_solve(co)

    with pytest.raises(services.InvalidState):
        services.start_solve(co)


def test_cannot_stop_before_solving(rnd, co):
    services.start_inspection(co)

    with pytest.raises(services.InvalidState):
        services.stop_solve(co, time_ms=1000)


def test_cannot_stop_twice(rnd, co):
    services.start_inspection(co)
    services.start_solve(co)
    services.stop_solve(co, time_ms=1000)

    with pytest.raises(services.InvalidState):
        services.stop_solve(co, time_ms=900)


@pytest.mark.parametrize("bad_time", [0, -5, 1.5, "12000", None, True])
def test_time_must_be_a_positive_whole_number_of_ms(rnd, co, bad_time):
    services.start_inspection(co)
    services.start_solve(co)

    with pytest.raises(services.InvalidInput):
        services.stop_solve(co, time_ms=bad_time)


def test_each_player_has_their_own_solve(rnd, co, challenge):
    other = next(p for p in challenge.players if not p.is_co)

    services.start_inspection(co)
    services.start_inspection(other)

    assert {s.player for s in rnd.solves} == {co, other}


def test_running_out_of_inspection_is_a_dnf(rnd, co):
    services.start_inspection(co)

    solve = services.inspection_expired(co)

    assert solve.result == SolveResult.DNF
    assert solve.time_ms is None
    assert solve.started_solve_at is None


def test_inspection_cannot_run_out_once_solving(rnd, co):
    services.start_inspection(co)
    services.start_solve(co)

    with pytest.raises(services.InvalidState):
        services.inspection_expired(co)


def test_inspection_cannot_run_out_before_it_starts(rnd, co):
    with pytest.raises(services.InvalidState):
        services.inspection_expired(co)


def test_inspection_running_out_for_the_last_player_completes_the_round(rnd, co, challenge):
    other = next(p for p in challenge.players if not p.is_co)
    services.start_inspection(co)
    services.start_solve(co)
    services.stop_solve(co, time_ms=9_000)
    services.start_inspection(other)

    services.inspection_expired(other)

    assert rnd.ended_at is not None
