import pytest

from app import services
from app.models import ChallengeStatus, RoundStatus, SolveResult


def finish(player, time_ms):
    services.start_inspection(player)
    services.start_solve(player)
    return services.stop_solve(player, time_ms=time_ms)


def results_by_name(rnd):
    return {s.player.display_name: (s.result, s.time_ms) for s in rnd.solves}


def test_co_ends_round_and_unfinished_connected_players_get_dnf(challenge, co, add_player, clock):
    done, solving, inspecting, idle = (
        add_player(n) for n in ("Done", "Solving", "Inspect", "Idle")
    )
    rnd = services.start_round(challenge, co)
    finish(done, 10_000)
    services.start_inspection(solving)
    services.start_solve(solving)
    services.start_inspection(inspecting)
    clock.advance(minutes=1)

    services.end_round(challenge, co)

    assert results_by_name(rnd) == {
        "Done": (SolveResult.OK, 10_000),
        "Solving": (SolveResult.DNF, None),
        "Inspect": (SolveResult.DNF, None),
        "Idle": (SolveResult.DNF, None),
        "Tom": (SolveResult.DNF, None),
    }
    assert rnd.status == RoundStatus.COMPLETE
    assert rnd.ended_at == clock.now.replace(tzinfo=None)
    assert challenge.status == ChallengeStatus.ROUND_RESULTS


def test_disconnected_players_who_never_started_get_no_result(challenge, co, add_player):
    add_player("Gone", connected=False)
    rnd = services.start_round(challenge, co)

    services.end_round(challenge, co)

    assert "Gone" not in results_by_name(rnd)


def test_only_the_co_can_end_a_round(challenge, co, add_player):
    guest = add_player("Guest")
    services.start_round(challenge, co)

    with pytest.raises(services.NotAllowed):
        services.end_round(challenge, guest)


def test_cannot_end_a_round_that_is_not_running(challenge, co):
    with pytest.raises(services.InvalidState):
        services.end_round(challenge, co)


def test_cannot_keep_solving_after_the_round_ends(challenge, co, add_player):
    other = add_player("Other")
    services.start_round(challenge, co)
    services.start_inspection(other)
    services.start_solve(other)
    services.end_round(challenge, co)

    with pytest.raises(services.InvalidState):
        services.stop_solve(other, time_ms=5_000)


def test_round_ends_itself_when_the_last_connected_player_finishes(challenge, co, add_player):
    other = add_player("Other")
    rnd = services.start_round(challenge, co)

    finish(co, 9_000)
    assert rnd.status == RoundStatus.ACTIVE

    finish(other, 11_000)
    assert rnd.status == RoundStatus.COMPLETE
    assert challenge.status == ChallengeStatus.ROUND_RESULTS


def test_disconnected_players_do_not_hold_the_round_open(challenge, co, add_player):
    add_player("Gone", connected=False)
    rnd = services.start_round(challenge, co)

    finish(co, 9_000)

    assert rnd.status == RoundStatus.COMPLETE


def test_leaderboard_ranks_finished_solves_and_skips_ones_in_progress(challenge, co, add_player):
    amy, bob, cat = (add_player(n) for n in ("Amy", "Bob", "Cat"))
    rnd = services.start_round(challenge, co)
    finish(amy, 10_000)
    finish(bob, 10_000)
    finish(co, 12_500)
    services.start_inspection(cat)

    assert services.leaderboard(rnd) == [
        {
            "player_id": str(amy.id),
            "display_name": "Amy",
            "time_ms": 10_000,
            "plus_two": False,
            "result": "ok",
            "position": 1,
            "points": 0,
        },
        {
            "player_id": str(bob.id),
            "display_name": "Bob",
            "time_ms": 10_000,
            "plus_two": False,
            "result": "ok",
            "position": 1,
            "points": 0,
        },
        {
            "player_id": str(co.id),
            "display_name": "Tom",
            "time_ms": 12_500,
            "plus_two": False,
            "result": "ok",
            "position": 3,
            "points": 0,
        },
    ]


def test_leaderboard_lists_dnfs_last(challenge, co, add_player):
    amy = add_player("Amy")
    rnd = services.start_round(challenge, co)
    finish(amy, 10_000)
    services.end_round(challenge, co)

    assert [(r["display_name"], r["result"], r["position"]) for r in services.leaderboard(rnd)] == [
        ("Amy", "ok", 1),
        ("Tom", "dnf", 2),
    ]


def test_a_late_start_cut_off_by_end_round_is_a_plain_dnf(challenge, co, add_player):
    amy = add_player("Amy")
    rnd = services.start_round(challenge, co)
    services.start_inspection(amy)
    services.start_solve(amy, plus_two=True)

    services.end_round(challenge, co)

    [row] = [r for r in services.leaderboard(rnd) if r["display_name"] == "Amy"]
    assert (row["result"], row["time_ms"], row["plus_two"]) == ("dnf", None, False)
