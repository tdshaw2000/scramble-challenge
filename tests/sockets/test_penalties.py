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


def results(update):
    return [
        (r["display_name"], r["result"], r["time_ms"], r["plus_two"]) for r in update["results"]
    ]


def test_everyone_sees_a_plus_two_while_the_round_is_still_going(challenge, add_player, connect):
    add_player("Amy", connected=False)
    tom, amy = join_all(challenge, connect, "cookie-co", "cookie-Amy")
    tom.emit("start_round", {})
    solve(tom, 12_000)
    amy.get_received()

    tom.emit("set_penalty", {"plus_two": True, "dnf": False})

    for client in (tom, amy):
        [update] = events(client, "leaderboard_update")
        assert results(update) == [("Tom", "ok", 14_000, True)]


def test_a_dnf_on_the_results_screen_moves_the_point_for_everyone(challenge, add_player, connect):
    add_player("Amy", connected=False)
    tom, amy = join_all(challenge, connect, "cookie-co", "cookie-Amy")
    tom.emit("start_round", {})
    solve(tom, 9_000)
    solve(amy, 12_000)
    tom.get_received()
    amy.get_received()

    tom.emit("set_penalty", {"plus_two": False, "dnf": True})

    for client in (tom, amy):
        received = client.get_received()
        [update] = [e["args"][0] for e in received if e["name"] == "leaderboard_update"]
        assert results(update) == [("Amy", "ok", 12_000, False), ("Tom", "dnf", None, False)]
        [player_list] = [e["args"][0] for e in received if e["name"] == "player_list"]
        assert {p["display_name"]: p["points"] for p in player_list} == {"Tom": 0, "Amy": 1}
        # The round isn't completing again, so nobody's screen resets.
        assert "round_complete" not in [e["name"] for e in received]


def test_a_change_that_isnt_allowed_is_reported_to_the_player_only(challenge, add_player, connect):
    add_player("Amy", connected=False)
    tom, amy = join_all(challenge, connect, "cookie-co", "cookie-Amy")
    tom.emit("start_round", {})
    amy.get_received()

    tom.emit("set_penalty", {"plus_two": True, "dnf": False})

    [error] = events(tom, "game_error")
    assert error["message"]
    assert amy.get_received() == []


def test_a_missing_choice_is_refused(challenge, add_player, connect):
    add_player("Amy", connected=False)
    tom, amy = join_all(challenge, connect, "cookie-co", "cookie-Amy")
    tom.emit("start_round", {})
    solve(tom, 9_000)
    tom.get_received()

    tom.emit("set_penalty", {"dnf": True})

    assert events(tom, "game_error")
