from app import sockets
from app.models import ChallengeStatus
from tests.conftest import events


def join(client, challenge):
    client.emit("join_challenge", {"challenge_slug": challenge.slug})
    return client


def test_leaving_shows_the_player_as_disconnected_to_everyone_else(challenge, add_player, connect):
    add_player("Amy", connected=False)
    tom = join(connect("cookie-co"), challenge)
    amy = join(connect("cookie-Amy"), challenge)
    tom.get_received()

    amy.disconnect()

    [player_list] = events(tom, "player_list")
    assert {p["display_name"]: p["connected"] for p in player_list} == {"Tom": True, "Amy": False}


def test_a_second_tab_closing_does_not_disconnect_the_player(challenge, add_player, connect):
    amy_player = add_player("Amy", connected=False)
    tom = join(connect("cookie-co"), challenge)
    join(connect("cookie-Amy"), challenge)
    second_tab = join(connect("cookie-Amy"), challenge)
    tom.get_received()

    second_tab.disconnect()

    assert events(tom, "player_list") == []
    assert amy_player.connected is True


def test_leaving_mid_round_posts_a_dnf_to_the_leaderboard(challenge, add_player, connect):
    add_player("Amy", connected=False)
    add_player("Bob", connected=False)
    tom = join(connect("cookie-co"), challenge)
    amy = join(connect("cookie-Amy"), challenge)
    join(connect("cookie-Bob"), challenge)
    tom.emit("start_round", {})
    amy.emit("start_inspection", {})
    tom.get_received()

    amy.disconnect()

    [update] = events(tom, "leaderboard_update")
    assert [(r["display_name"], r["result"]) for r in update["results"]] == [("Amy", "dnf")]


def test_leaving_as_the_last_unfinished_player_completes_the_round(challenge, add_player, connect):
    add_player("Amy", connected=False)
    tom = join(connect("cookie-co"), challenge)
    amy = join(connect("cookie-Amy"), challenge)
    tom.emit("start_round", {})
    for event, payload in [
        ("start_inspection", {}),
        ("start_solve", {}),
        ("stop_solve", {"time_ms": 9_000}),
    ]:
        tom.emit(event, payload)
    tom.get_received()

    amy.disconnect()

    assert [e["name"] for e in tom.get_received()] == [
        "player_list",
        "leaderboard_update",
        "round_complete",
        "player_list",
    ]


def test_disconnecting_without_joining_is_harmless(challenge, connect):
    connect("cookie-co").disconnect()

    assert challenge.status == ChallengeStatus.WAITING


def test_challenge_ends_for_everyone_when_the_co_does_not_come_back(
    app, challenge, add_player, connect, clock
):
    add_player("Amy", connected=False)
    tom = join(connect("cookie-co"), challenge)
    amy = join(connect("cookie-Amy"), challenge)
    tom.disconnect()
    amy.get_received()

    sockets.end_abandoned_challenges()
    assert events(amy, "challenge_ended") == []

    clock.advance(seconds=app.config["CO_GRACE_SECONDS"])
    sockets.end_abandoned_challenges()
    assert events(amy, "challenge_ended") == [{}]


def test_co_refreshing_within_the_grace_period_keeps_the_challenge(
    app, challenge, add_player, connect, clock
):
    add_player("Amy", connected=False)
    tom = join(connect("cookie-co"), challenge)
    amy = join(connect("cookie-Amy"), challenge)
    tom.disconnect()
    clock.advance(seconds=5)
    join(connect("cookie-co"), challenge)
    amy.get_received()

    clock.advance(seconds=app.config["CO_GRACE_SECONDS"])
    sockets.end_abandoned_challenges()

    assert events(amy, "challenge_ended") == []


def test_joining_an_ended_challenge_is_told_it_ended(app, challenge, connect, clock):
    # A tab that slept through the end hears about it when it reconnects, and its page
    # then reloads into the summary.
    join(connect("cookie-co"), challenge).disconnect()
    clock.advance(seconds=app.config["CO_GRACE_SECONDS"])
    sockets.end_abandoned_challenges()

    tom = join(connect("cookie-co"), challenge)

    received = tom.get_received()
    assert [e["name"] for e in received] == ["challenge_ended"]
    assert challenge.co_player.connected is False
