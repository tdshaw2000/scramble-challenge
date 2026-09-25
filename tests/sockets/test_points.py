from tests.conftest import events


def join_all(challenge, connect, *cookie_ids):
    clients = [connect(c) for c in cookie_ids]
    for client in clients:
        client.emit("join_challenge", {"challenge_slug": challenge.slug})
    for client in clients:
        client.get_received()
    return clients


def solve(client, time_ms):
    client.emit("start_inspection", {})
    client.emit("start_solve", {})
    client.emit("stop_solve", {"time_ms": time_ms})


def points(player_list):
    return {p["display_name"]: p["points"] for p in player_list}


def test_everyone_sees_the_winners_new_points_when_the_last_player_finishes(
    challenge, add_player, connect
):
    add_player("Amy", connected=False)
    tom, amy = join_all(challenge, connect, "cookie-co", "cookie-Amy")
    tom.emit("start_round", {})
    solve(tom, 12_000)

    solve(amy, 9_000)

    for client in (tom, amy):
        [player_list] = events(client, "player_list")
        assert points(player_list) == {"Tom": 0, "Amy": 1}


def test_everyone_sees_new_points_when_the_co_ends_the_round(challenge, add_player, connect):
    add_player("Amy", connected=False)
    tom, amy = join_all(challenge, connect, "cookie-co", "cookie-Amy")
    tom.emit("start_round", {})
    solve(tom, 12_000)
    amy.get_received()

    tom.emit("end_round", {})

    [player_list] = events(amy, "player_list")
    assert points(player_list) == {"Tom": 1, "Amy": 0}


def test_results_carry_each_players_points_so_far(challenge, add_player, connect):
    add_player("Amy", connected=False)
    tom, amy = join_all(challenge, connect, "cookie-co", "cookie-Amy")
    tom.emit("start_round", {})
    solve(tom, 9_000)
    solve(amy, 12_000)
    tom.emit("start_round", {})
    tom.get_received()

    solve(amy, 8_000)

    [update] = events(tom, "leaderboard_update")
    assert [(r["display_name"], r["points"]) for r in update["results"]] == [("Amy", 0)]
    solve(tom, 10_000)
    [complete] = events(tom, "round_complete")
    assert [(r["display_name"], r["points"]) for r in complete["results"]] == [
        ("Amy", 1),
        ("Tom", 1),
    ]


def test_a_player_joining_later_sees_the_points_so_far(challenge, add_player, connect):
    add_player("Amy", connected=False)
    [tom] = join_all(challenge, connect, "cookie-co")
    tom.emit("start_round", {})
    solve(tom, 9_000)

    amy = connect("cookie-Amy")
    amy.emit("join_challenge", {"challenge_slug": challenge.slug})

    [player_list] = events(amy, "player_list")
    assert points(player_list) == {"Tom": 1, "Amy": 0}
