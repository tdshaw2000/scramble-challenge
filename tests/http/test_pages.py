import io
import re

import segno

from app import services
from app.routes import COOKIE_NAME


def cookie(client):
    found = client.get_cookie(COOKIE_NAME)
    return found.value if found else None


def svg_of(qr):
    out = io.BytesIO()
    qr.save(out, kind="svg", scale=10, border=4, xmldecl=False)
    return out.getvalue()


def create(client, name="Tom"):
    return client.post("/challenges", data={"display_name": name})


def test_landing_page_offers_to_start_a_challenge(client):
    response = client.get("/")

    assert response.status_code == 200
    assert b'name="display_name"' in response.data
    assert b"Start new challenge" in response.data


def test_starting_a_challenge_sets_a_device_cookie_and_goes_to_the_challenge(client):
    response = create(client)

    assert response.status_code == 302
    slug = re.fullmatch(r"/c/([\w-]+)", response.headers["Location"]).group(1)
    challenge = services.get_challenge(slug)
    assert challenge.co_player.display_name == "Tom"
    assert challenge.co_player.cookie_id == cookie(client)


def test_device_cookie_is_long_lived_and_hidden_from_scripts(client):
    response = create(client)

    set_cookie = response.headers["Set-Cookie"]
    assert "HttpOnly" in set_cookie
    assert "SameSite=Lax" in set_cookie
    assert "Max-Age=" in set_cookie


def test_the_same_device_keeps_its_cookie_across_challenges(client):
    create(client)
    first = cookie(client)

    create(client, "Tom again")

    assert cookie(client) == first


def test_blank_name_redisplays_the_form_with_an_error(client):
    response = create(client, "  ")

    assert response.status_code == 400
    assert b"Name must be" in response.data


def test_co_sees_share_link_and_puzzle_choice(client):
    location = create(client).headers["Location"]

    response = client.get(location)

    assert response.status_code == 200
    assert f"http://localhost{location}".encode() in response.data
    assert b'<option value="333" selected>' in response.data


def test_puzzle_choice_lists_every_puzzle_by_name(client):
    location = create(client).headers["Location"]

    page = client.get(location).text
    options = re.findall(r'<option value="([^"]+)"[^>]*>([^<]+)</option>', page)

    assert options == [
        ("222", "2x2"),
        ("333", "3x3"),
        ("444", "4x4"),
        ("555", "5x5"),
        ("666", "6x6"),
        ("777", "7x7"),
        ("pyram", "Pyraminx"),
        ("skewb", "Skewb"),
        ("sq1", "Square-1"),
        ("minx", "Megaminx"),
        ("clock", "Clock"),
    ]


def test_visitor_without_a_player_is_asked_for_a_name(app, client, challenge):
    response = client.get(f"/c/{challenge.slug}")

    assert response.status_code == 200
    assert b'name="display_name"' in response.data
    assert b"Join" in response.data
    assert b"Start round" not in response.data


def test_joining_through_the_form_adds_the_player(client, challenge):
    response = client.post(f"/c/{challenge.slug}/join", data={"display_name": "Amy"})

    assert response.status_code == 302
    assert response.headers["Location"] == f"/c/{challenge.slug}"
    amy = services.player_for_cookie(challenge, cookie(client))
    assert amy.display_name == "Amy"
    assert amy.is_co is False


def test_joined_player_sees_the_waiting_message_not_co_controls(client, challenge):
    client.post(f"/c/{challenge.slug}/join", data={"display_name": "Amy"})

    response = client.get(f"/c/{challenge.slug}")

    assert b"Waiting for the challenge owner" in response.data
    assert b"Start round" not in response.data


def test_the_players_list_shows_points_after_names(client, challenge, co):
    client.post(f"/c/{challenge.slug}/join", data={"display_name": "Amy"})
    services.start_round(challenge, co)
    services.start_inspection(co)
    services.start_solve(co)
    services.stop_solve(co, 9_000)
    services.complete_round(challenge)

    html = client.get(f"/c/{challenge.slug}").data.decode()

    # Both joined at the same fake-clock moment, so their order isn't fixed.
    assert sorted(re.findall(r'<li class="player">(.*?)</li>', html)) == [
        "Amy (0)",
        "Tom (1) (owner)",
    ]


def test_join_with_blank_name_redisplays_the_form(client, challenge):
    response = client.post(f"/c/{challenge.slug}/join", data={"display_name": ""})

    assert response.status_code == 400
    assert b"Name must be" in response.data


def test_unknown_challenge_is_404(client):
    assert client.get("/c/nope").status_code == 404
    assert client.post("/c/nope/join", data={"display_name": "Amy"}).status_code == 404


def test_round_scramble_image_is_served_as_svg(client, challenge, co):
    services.start_round(challenge, co)

    response = client.get(f"/c/{challenge.slug}/rounds/1/scramble.svg")

    assert response.status_code == 200
    assert response.mimetype == "image/svg+xml"
    assert response.data == b"<svg>333 1</svg>"
    assert response.headers["X-Content-Type-Options"] == "nosniff"


def test_missing_round_image_is_404(client, challenge):
    assert client.get(f"/c/{challenge.slug}/rounds/1/scramble.svg").status_code == 404


def test_challenge_page_loads_the_socket_client_with_the_slug(client, challenge):
    client.set_cookie(COOKIE_NAME, "cookie-co")

    response = client.get(f"/c/{challenge.slug}")

    assert f'data-slug="{challenge.slug}"'.encode() in response.data
    assert b'data-is-co="true"' in response.data
    assert b"socket.io" in response.data
    assert b"/static/challenge.js" in response.data


def test_co_start_round_button_starts_disabled_until_the_socket_joins(client, challenge):
    # challenge.js enables it once the join is confirmed (tests/e2e/test_join_race.py).
    client.set_cookie(COOKIE_NAME, "cookie-co")

    response = client.get(f"/c/{challenge.slug}")

    assert b'id="start-round" class="button button-primary" disabled' in response.data


def test_socket_client_script_is_served(client):
    response = client.get("/static/challenge.js")

    assert response.status_code == 200
    assert b"join_challenge" in response.data


def test_co_gets_qr_code_and_share_url_buttons_instead_of_a_link_box(client):
    location = create(client).headers["Location"]

    page = client.get(location).text

    assert "Share with others" in page
    assert re.search(r'<button[^>]*id="qr-button"[^>]*>QR code</button>', page)
    assert re.search(
        rf'<button[^>]*id="share-link-button"[^>]*data-url="http://localhost{location}"'
        r"[^>]*>Share URL</button>",
        page,
    )
    assert 'id="share-link"' not in page
    assert f'src="{location}/qr.svg"' in page


def test_other_players_get_no_share_buttons(client):
    location = create(client).headers["Location"]
    client.delete_cookie(COOKIE_NAME)
    client.post(f"{location}/join", data={"display_name": "Amy"})

    page = client.get(location).text

    assert 'id="qr-button"' not in page
    assert 'id="share-link-button"' not in page


def test_qr_code_is_an_svg_of_the_challenge_link(client):
    location = create(client).headers["Location"]

    response = client.get(f"{location}/qr.svg")

    assert response.status_code == 200
    assert response.mimetype == "image/svg+xml"
    expected = segno.make(f"http://localhost{location}", error="m")
    assert response.data == svg_of(expected)


def test_qr_code_for_an_unknown_challenge_is_not_found(client):
    assert client.get("/c/nope/qr.svg").status_code == 404
