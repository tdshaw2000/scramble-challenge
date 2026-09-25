"""The owner can't start a round before the page has joined the challenge over the socket.

The player list is drawn by the page itself, so it shows before the socket join finishes.
A Start round click in that gap used to fail with "Join the challenge first."
"""

from playwright.sync_api import expect

from tests.e2e.test_game import start_challenge


def test_start_round_stays_disabled_until_the_page_has_joined(new_player, live_server):
    tom = new_player()
    tom.route("**/socket.io/**", lambda route: route.abort())

    start_challenge(tom)

    expect(tom.get_by_role("button", name="Start round")).to_be_disabled()


def test_start_round_is_enabled_once_the_page_has_joined(new_player, live_server):
    tom = new_player()

    start_challenge(tom)

    expect(tom.get_by_role("button", name="Start round")).to_be_enabled()
