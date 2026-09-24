import pytest
import requests
import responses

from app.tnoodle import Scramble, TNoodleClient, TNoodleError

BASE = "http://tnoodle.test:2014"


@responses.activate
def test_generate_fetches_scramble_then_its_svg():
    responses.get(f"{BASE}/api/v0/scramble/333", json=["R U R' U'"])
    responses.get(
        f"{BASE}/api/v0/view/333/svg",
        match=[responses.matchers.query_param_matcher({"scramble": "R U R' U'"})],
        body="<svg>cube</svg>",
    )

    scramble = TNoodleClient(BASE).generate("333")

    assert scramble == Scramble(text="R U R' U'", svg="<svg>cube</svg>")


@responses.activate
def test_unknown_puzzle_raises_tnoodle_error():
    responses.get(f"{BASE}/api/v0/scramble/nope", status=404)

    with pytest.raises(TNoodleError):
        TNoodleClient(BASE).generate("nope")


@responses.activate
def test_svg_failure_raises_tnoodle_error():
    responses.get(f"{BASE}/api/v0/scramble/333", json=["R U"])
    responses.get(f"{BASE}/api/v0/view/333/svg", status=500)

    with pytest.raises(TNoodleError):
        TNoodleClient(BASE).generate("333")


@responses.activate
def test_unreachable_server_raises_tnoodle_error():
    responses.get(f"{BASE}/api/v0/scramble/333", body=requests.ConnectionError("down"))

    with pytest.raises(TNoodleError):
        TNoodleClient(BASE).generate("333")
