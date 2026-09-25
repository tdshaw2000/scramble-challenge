import pytest

from app.models import ChallengeStatus
from tests.conftest import events


@pytest.fixture
def joined(challenge, connect):
    """Connect and join as the browser holding `cookie_id`; clears the join chatter."""

    def join(cookie_id):
        client = connect(cookie_id)
        client.emit("join_challenge", {"challenge_slug": challenge.slug})
        return client

    def join_all(*cookie_ids):
        clients = [join(c) for c in cookie_ids]
        for client in clients:
            client.get_received()
        return clients

    return join_all


def solve(client, time_ms):
    client.emit("start_inspection", {})
    client.emit("start_solve", {})
    client.emit("stop_solve", {"time_ms": time_ms})


def test_co_starting_a_round_sends_the_scramble_to_everyone(challenge, add_player, joined):
    add_player("Amy", connected=False)
    tom, amy = joined("cookie-co", "cookie-Amy")

    tom.emit("start_round", {"puzzle": "333"})

    for client in (tom, amy):
        [started] = events(client, "round_started")
        assert started["round_number"] == 1
        assert started["scramble_text"] == "R U R' U' 1"
    assert challenge.status == ChallengeStatus.ROUND_ACTIVE


def test_start_round_without_a_puzzle_uses_the_default(challenge, joined):
    [tom] = joined("cookie-co")

    tom.emit("start_round", {})

    [started] = events(tom, "round_started")
    assert started["puzzle"] == "333"


def test_round_started_names_the_puzzle_so_players_know_what_to_pick_up(challenge, joined):
    [tom] = joined("cookie-co")

    tom.emit("start_round", {"puzzle": "minx"})

    [started] = events(tom, "round_started")
    assert started["puzzle"] == "minx"
    assert started["puzzle_name"] == "Megaminx"


def test_only_the_co_can_start_a_round(challenge, add_player, joined):
    add_player("Amy", connected=False)
    tom, amy = joined("cookie-co", "cookie-Amy")

    amy.emit("start_round", {"puzzle": "333"})

    assert events(amy, "game_error") == [{"message": "Only the challenge owner can do that."}]
    assert events(tom, "round_started") == []


def test_actions_before_joining_are_refused(challenge, connect):
    client = connect("cookie-co")

    client.emit("start_round", {"puzzle": "333"})

    assert events(client, "game_error") == [{"message": "Join the challenge first."}]


def test_tnoodle_failure_is_reported_to_the_co(challenge, tnoodle, joined):
    [tom] = joined("cookie-co")
    tnoodle.fail = True

    tom.emit("start_round", {"puzzle": "333"})

    assert events(tom, "game_error") == [{"message": "Couldn't get a scramble; try again."}]


def test_a_finished_solve_updates_everyones_leaderboard(challenge, add_player, joined):
    add_player("Amy", connected=False)
    tom, amy = joined("cookie-co", "cookie-Amy")
    tom.emit("start_round", {})
    tom.get_received()
    amy.get_received()

    solve(amy, 9_500)

    for client in (tom, amy):
        [update] = events(client, "leaderboard_update")
        assert update["round_id"] == str(challenge.current_round.id)
        assert [(r["display_name"], r["time_ms"], r["position"]) for r in update["results"]] == [
            ("Amy", 9_500, 1)
        ]


def test_bad_solve_messages_are_reported_to_the_sender(challenge, joined):
    [tom] = joined("cookie-co")
    tom.emit("start_round", {})
    tom.emit("start_solve", {})

    assert events(tom, "game_error")[0]["message"].startswith("Start inspection first")


def test_bad_time_is_reported(challenge, joined):
    [tom] = joined("cookie-co")
    tom.emit("start_round", {})
    tom.emit("start_inspection", {})
    tom.emit("start_solve", {})
    tom.get_received()

    tom.emit("stop_solve", {"time_ms": "fast"})

    assert events(tom, "game_error") == [{"message": "time_ms must be a positive whole number."}]


def test_last_player_finishing_completes_the_round_for_everyone(challenge, add_player, joined):
    add_player("Amy", connected=False)
    tom, amy = joined("cookie-co", "cookie-Amy")
    tom.emit("start_round", {})
    solve(tom, 12_000)
    tom.get_received()

    solve(amy, 9_000)

    received = tom.get_received()
    names = [e["name"] for e in received]
    assert names == ["leaderboard_update", "round_complete", "player_list"]
    complete = received[1]["args"][0]
    assert [(r["display_name"], r["position"]) for r in complete["results"]] == [
        ("Amy", 1),
        ("Tom", 2),
    ]
    assert challenge.status == ChallengeStatus.ROUND_RESULTS


def test_co_ending_the_round_sends_final_results_with_dnfs(challenge, add_player, joined):
    add_player("Amy", connected=False)
    tom, amy = joined("cookie-co", "cookie-Amy")
    tom.emit("start_round", {})
    solve(tom, 12_000)
    amy.get_received()

    tom.emit("end_round", {})

    [complete] = events(amy, "round_complete")
    assert [(r["display_name"], r["result"]) for r in complete["results"]] == [
        ("Tom", "ok"),
        ("Amy", "dnf"),
    ]


def test_only_the_co_can_end_the_round(challenge, add_player, joined):
    add_player("Amy", connected=False)
    tom, amy = joined("cookie-co", "cookie-Amy")
    tom.emit("start_round", {})

    amy.emit("end_round", {})

    assert events(amy, "game_error") == [{"message": "Only the challenge owner can do that."}]
    assert challenge.status == ChallengeStatus.ROUND_ACTIVE


def test_running_out_of_inspection_posts_a_dnf_to_everyone(challenge, add_player, joined):
    add_player("Amy", connected=False)
    tom, amy = joined("cookie-co", "cookie-Amy")
    tom.emit("start_round", {})
    tom.get_received()
    amy.emit("start_inspection", {})
    amy.get_received()

    amy.emit("inspection_expired", {})

    for client in (tom, amy):
        [update] = events(client, "leaderboard_update")
        assert [(r["display_name"], r["result"]) for r in update["results"]] == [("Amy", "dnf")]


def test_inspection_expiring_without_inspecting_is_reported(challenge, joined):
    [tom] = joined("cookie-co")
    tom.emit("start_round", {})
    tom.get_received()

    tom.emit("inspection_expired", {})

    assert events(tom, "game_error") == [{"message": "No inspection in progress."}]


def test_co_ending_the_challenge_sends_everyone_to_the_summary(challenge, add_player, joined):
    add_player("Amy", connected=False)
    tom, amy = joined("cookie-co", "cookie-Amy")
    tom.emit("start_round", {})
    tom.emit("end_round", {})
    tom.get_received()
    amy.get_received()

    tom.emit("end_challenge", {})

    for client in (tom, amy):
        assert events(client, "challenge_ended") == [{}]
    assert challenge.status == ChallengeStatus.ENDED


def test_only_the_co_can_end_the_challenge(challenge, add_player, joined):
    add_player("Amy", connected=False)
    tom, amy = joined("cookie-co", "cookie-Amy")
    tom.emit("start_round", {})
    tom.emit("end_round", {})
    tom.get_received()

    amy.emit("end_challenge", {})

    assert events(amy, "game_error") == [{"message": "Only the challenge owner can do that."}]
    assert events(tom, "challenge_ended") == []
    assert challenge.status == ChallengeStatus.ROUND_RESULTS


def test_ending_the_challenge_mid_round_is_refused(challenge, joined):
    [tom] = joined("cookie-co")
    tom.emit("start_round", {})
    tom.get_received()

    tom.emit("end_challenge", {})

    assert events(tom, "game_error") == [
        {"message": "The challenge can only be ended between rounds, once one has finished."}
    ]
    assert events(tom, "challenge_ended") == []
