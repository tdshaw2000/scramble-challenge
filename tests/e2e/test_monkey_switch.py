"""The Monkey skin's timed-inspection switch reads clearly as on or off: its track changes
colour, and its knob stands out from the track either way."""

from tests.e2e.test_dark_skin import contrast
from tests.e2e.test_game import start_challenge

SWITCH_COLOURS = """() => ({
  track: getComputedStyle(document.querySelector('.switch-track')).backgroundColor,
  knob: getComputedStyle(document.querySelector('.switch-thumb')).backgroundColor,
})"""


def test_the_switch_looks_different_on_and_off(new_player, live_server):
    tom = new_player()
    tom.context.add_cookies(
        [{"name": "scramble_skin", "value": "monkeyisland2", "url": live_server}]
    )
    start_challenge(tom)
    switch = tom.get_by_label("Timed inspection")

    switch.check()
    on = tom.evaluate(SWITCH_COLOURS)
    switch.uncheck()
    off = tom.evaluate(SWITCH_COLOURS)

    assert on["track"] != off["track"], (on, off)
    # 3:1 is the WCAG minimum for parts of a control.
    for state in (on, off):
        assert contrast(state["knob"], state["track"]) >= 3, (on, off)
