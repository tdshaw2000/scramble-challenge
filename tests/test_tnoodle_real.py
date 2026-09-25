"""The one test against a real TNoodle server: checks our assumptions about its API
still match reality. Deselected by default; run with `pytest -m tnoodle`
(TNOODLE_URL defaults to http://localhost:2014)."""

import os

import pytest

from app.services import SUPPORTED_PUZZLES
from app.tnoodle import TNoodleClient

pytestmark = pytest.mark.tnoodle


def test_real_tnoodle_returns_a_3x3_scramble_and_svg():
    client = TNoodleClient(os.environ.get("TNOODLE_URL", "http://localhost:2014"))

    scramble = client.generate("333")

    assert len(scramble.text.split()) >= 15
    assert set("".join(scramble.text.split())) <= set("UDLRFB'2")
    assert scramble.svg.lstrip().startswith("<svg")


@pytest.mark.parametrize("puzzle", SUPPORTED_PUZZLES)
def test_real_tnoodle_scrambles_every_puzzle_we_offer(puzzle):
    client = TNoodleClient(os.environ.get("TNOODLE_URL", "http://localhost:2014"))

    scramble = client.generate(puzzle)

    assert scramble.text.strip()
    assert scramble.svg.lstrip().startswith("<svg")
