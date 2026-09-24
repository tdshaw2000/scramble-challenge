from app import services
from tests.conftest import events


def join(client, challenge):
    client.emit("join_challenge", {"challenge_slug": challenge.slug})


def test_joining_marks_the_player_connected_and_broadcasts_the_player_list(
    challenge, co, connect
):
    client = connect("cookie-co")

    join(client, challenge)

    assert events(client, "player_list") == [
        [{"player_id": str(co.id), "display_name": "Tom", "is_co": True, "connected": True}]
    ]
    assert co.connected is True


def test_everyone_in_the_room_sees_a_new_player_arrive(challenge, co, add_player, connect):
    amy = add_player("Amy", connected=False)
    co_client = connect("cookie-co")
    join(co_client, challenge)
    co_client.get_received()

    join(connect("cookie-Amy"), challenge)

    [player_list] = events(co_client, "player_list")
    assert {p["display_name"]: p["connected"] for p in player_list} == {"Tom": True, "Amy": True}
    assert amy.connected is True


def test_rooms_are_per_challenge(challenge, connect):
    other = services.create_challenge("Zed", "cookie-zed")
    zed = connect("cookie-zed")
    zed.emit("join_challenge", {"challenge_slug": other.slug})
    zed.get_received()

    join(connect("cookie-co"), challenge)

    assert events(zed, "player_list") == []


def test_a_browser_with_no_player_in_this_challenge_is_refused(challenge, connect):
    stranger = connect("cookie-stranger")

    join(stranger, challenge)

    assert events(stranger, "game_error") == [{"message": "Enter your name to join first."}]


def test_cookie_id_in_the_payload_is_ignored(challenge, connect):
    stranger = connect("cookie-stranger")

    stranger.emit(
        "join_challenge",
        {"challenge_slug": challenge.slug, "cookie_id": "cookie-co", "display_name": "Tom"},
    )

    assert events(stranger, "game_error") == [{"message": "Enter your name to join first."}]
    assert challenge.co_player.connected is True  # set by the fixture, untouched


def test_unknown_challenge_is_refused(connect):
    client = connect("cookie-co")

    client.emit("join_challenge", {"challenge_slug": "nope"})

    assert events(client, "game_error") == [{"message": "Challenge not found."}]


def test_joining_mid_round_gets_the_current_scramble(challenge, co, add_player, connect):
    add_player("Amy", connected=False)
    rnd = services.start_round(challenge, co)
    amy = connect("cookie-Amy")

    join(amy, challenge)

    assert events(amy, "round_started") == [
        {
            "round_id": str(rnd.id),
            "round_number": 1,
            "puzzle": "333",
            "scramble_text": "R U R' U' 1",
            "scramble_svg_url": f"/c/{challenge.slug}/rounds/1/scramble.svg",
        }
    ]


def test_joining_during_results_shows_the_last_results(challenge, co, add_player, connect):
    add_player("Amy", connected=False)
    rnd = services.start_round(challenge, co)
    services.end_round(challenge, co)
    amy = connect("cookie-Amy")

    join(amy, challenge)

    assert events(amy, "round_started") == []
    [complete] = events(amy, "round_complete")
    assert complete["round_id"] == str(rnd.id)
    assert [r["display_name"] for r in complete["results"]] == ["Tom"]
