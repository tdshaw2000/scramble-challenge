"""The owner can't start a round before the page has joined the challenge over the socket.

The player list is drawn by the page itself, so it shows before the socket join finishes.
A Start round click in that gap used to fail with "Join the challenge first."
"""

from playwright.sync_api import expect

from tests.e2e.test_game import start_challenge


def test_start_round_stays_disabled_until_the_page_has_joined(new_player, live_server):
    tom = new_player()
    tom.route("**/socket.io/**", lambda route: route.abort())

    tom.goto("/")
    tom.get_by_label("Your name").fill("Tom")
    tom.get_by_role("button", name="Start new challenge").click()
    expect(tom.locator("#players")).to_contain_text("Tom")

    expect(tom.get_by_role("button", name="Start round")).to_be_disabled()


def test_start_round_is_enabled_once_the_page_has_joined(new_player, live_server):
    tom = new_player()

    start_challenge(tom)

    expect(tom.get_by_role("button", name="Start round")).to_be_enabled()


# Keeps a handle on the page's socket so a test can drop its connection.
CAPTURE_SOCKET = """
  let realIo;
  Object.defineProperty(window, "io", {
    configurable: true,
    get() { return realIo; },
    set(io) {
      realIo = Object.assign((...args) => (window.__socket = io(...args)), io);
    },
  });
"""


def test_start_round_is_disabled_again_while_reconnecting(new_player, live_server):
    tom = new_player()
    tom.add_init_script(CAPTURE_SOCKET)
    start_challenge(tom)
    button = tom.get_by_role("button", name="Start round")
    expect(button).to_be_enabled()

    tom.route("**/socket.io/**", lambda route: route.abort())
    tom.evaluate("window.__socket.io.engine.close()")

    expect(button).to_be_disabled()
    tom.unroute("**/socket.io/**")
    expect(button).to_be_enabled()
