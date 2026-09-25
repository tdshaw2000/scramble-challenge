"""Puzzles other than 3x3: everyone is told which one, and long scrambles still fit a phone."""

import urllib.parse

import pytest
from playwright.sync_api import expect

from tests.e2e.conftest import control
from tests.e2e.test_game import join, start_challenge

# Real TNoodle 1.2.3 output, so the layout is tested against true lengths.
SCRAMBLES = {
    "6x6": "L F2 Dw2 B2 R' Uw Rw2 Dw D2 L' Lw' Fw2 L2 U 3Rw 3Uw Bw L2 Lw Uw' D2 Lw' D2 R2 B' 3Uw Rw' U Dw2 Bw' 3Fw' Dw2 B' Bw' U Uw2 3Fw U Rw U Dw' D F2 Lw2 Uw2 Bw' F U' 3Uw Uw F Rw F2 R' Lw F' Dw' 3Uw 3Fw' B Rw' Dw2 Rw2 3Fw' B Rw2 F2 3Uw F' Bw' Rw2 U2 F 3Fw2 D L' 3Fw Uw' F2 3Fw2",  # noqa: E501
    "7x7": "Dw2 3Rw2 3Lw2 Dw2 U' 3Uw' Rw2 R Fw' R2 3Dw F2 3Bw' 3Rw' D2 Fw 3Lw2 U 3Rw' Fw B2 D2 3Dw2 Fw2 3Dw Uw' Fw' 3Bw Lw2 Dw 3Lw Bw2 3Bw L2 3Uw' L Uw 3Bw Dw D' Lw 3Bw2 3Dw Lw' Rw2 B' 3Dw 3Uw L' 3Uw 3Dw' Rw2 3Lw' U' 3Lw2 3Rw2 R' Uw Bw' Fw2 3Bw 3Uw Bw2 B Rw2 3Uw L2 3Dw' U D2 F2 Lw B R2 3Bw' F' 3Rw F2 3Bw L' 3Uw' Rw2 3Bw' Fw2 F' 3Uw Bw2 U 3Fw Bw2 B 3Rw Lw2 3Bw Fw Dw' R 3Uw' B2 3Bw",  # noqa: E501
    "Megaminx": "R-- D-- R-- D++ R++ D-- R++ D++ R-- D++ U\nR-- D-- R-- D++ R++ D-- R++ D-- R++ D++ U\nR-- D++ R++ D++ R-- D-- R-- D++ R++ D-- U'\nR++ D++ R-- D-- R-- D++ R++ D-- R++ D-- U'\nR-- D++ R-- D++ R++ D-- R++ D-- R++ D-- U'\nR-- D++ R++ D-- R-- D++ R++ D-- R++ D++ U\nR-- D-- R++ D++ R++ D-- R++ D++ R++ D++ U",  # noqa: E501
    "Square-1": "(-2,-3) / (-4,5) / (-3,-3) / (-5,-2) / (0,-1) / (3,0) / (0,-3) / (0,-4) / (-4,0) / (0,-2) / (-4,0) / (-5,0) /",  # noqa: E501
}


def start_round_with(live_server, page, label, text):
    control(live_server, "next-scramble", text=urllib.parse.quote(text))
    page.get_by_label("Puzzle").select_option(label=label)
    page.get_by_role("button", name="Start round").click()
    expect(page.locator("#scramble-text")).to_have_text(text.replace("\n", " "))


def test_everyone_sees_which_puzzle_the_round_is_for(new_player, live_server):
    tom, amy = new_player(), new_player()
    join(amy, start_challenge(tom), "Amy")

    tom.get_by_label("Puzzle").select_option(label="Megaminx")
    tom.get_by_role("button", name="Start round").click()

    for page in (tom, amy):
        expect(page.get_by_role("heading", name="Round 1: Megaminx")).to_be_visible()


@pytest.mark.parametrize("label", SCRAMBLES)
def test_long_scrambles_fit_on_a_phone_screen_without_scrolling(new_player, live_server, label):
    tom = new_player()
    start_challenge(tom)

    start_round_with(live_server, tom, label, SCRAMBLES[label])

    fits = tom.evaluate(
        """() => {
          const box = document.getElementById("scramble-text").getBoundingClientRect();
          return {
            sideways: document.documentElement.scrollWidth <= window.innerWidth,
            onFirstScreen: box.bottom <= window.innerHeight,
          };
        }"""
    )
    assert fits == {"sideways": True, "onFirstScreen": True}


def test_megaminx_shows_one_scramble_line_per_row(new_player, live_server):
    tom = new_player()
    start_challenge(tom)

    start_round_with(live_server, tom, "Megaminx", SCRAMBLES["Megaminx"])

    rows = tom.evaluate(
        """() => {
          const el = document.getElementById("scramble-text");
          const style = getComputedStyle(el);
          const padding = parseFloat(style.paddingTop) + parseFloat(style.paddingBottom);
          const height = el.clientHeight - padding;
          return Math.round(height / parseFloat(style.lineHeight));
        }"""
    )
    assert rows == 7
