"""Each player can choose to see their time running while they solve; it is off by default
and the choice is remembered in a cookie."""

import re

import pytest

from app.routes import COOKIE_NAME, SHOW_TIME_COOKIE_NAME


def show_time_button(client, challenge) -> str:
    client.set_cookie(COOKIE_NAME, "cookie-co")
    html = client.get(f"/c/{challenge.slug}").data.decode()
    match = re.search(r'<button[^>]*id="show-time"[^>]*>[^<]*</button>', html)
    assert match
    return match.group(0)


def test_the_show_time_toggle_sits_under_start_inspection(client, challenge):
    client.set_cookie(COOKIE_NAME, "cookie-co")
    html = client.get(f"/c/{challenge.slug}").data.decode()

    start = html.index('id="scramble"')
    scramble_card = html[start : html.index("</section>", start)]
    assert scramble_card.index('id="start-inspection"') < scramble_card.index('id="show-time"')


def test_the_time_is_hidden_while_solving_by_default(client, challenge):
    button = show_time_button(client, challenge)

    assert 'aria-pressed="false"' in button
    assert "Show time: Off" in button


def test_a_player_who_turned_it_on_sees_it_on(client, challenge):
    client.set_cookie(SHOW_TIME_COOKIE_NAME, "on")
    button = show_time_button(client, challenge)

    assert 'aria-pressed="true"' in button
    assert "Show time: On" in button


@pytest.mark.parametrize("value", ["off", "", "yes", "ON"])
def test_anything_but_on_in_the_cookie_means_off(client, challenge, value):
    client.set_cookie(SHOW_TIME_COOKIE_NAME, value)

    assert 'aria-pressed="false"' in show_time_button(client, challenge)


def test_the_overlay_has_a_place_for_the_running_time(client, challenge):
    client.set_cookie(COOKIE_NAME, "cookie-co")
    html = client.get(f"/c/{challenge.slug}").data.decode()

    overlay = html[html.index('id="overlay"') :]
    assert re.search(r'<p id="running-time" class="running-time" hidden>', overlay)
