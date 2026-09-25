import re
from datetime import UTC, datetime

import pytest

from app import services


def results(html: bytes) -> list[str]:
    """Each result row as 'position name time', tags stripped."""
    found = re.findall(r'<li class="result[^"]*">(.*?)</li>', html.decode(), re.S)
    return [" ".join(re.sub(r"<[^>]+>", " ", row).split()) for row in found]


def finish(player, time_ms):
    services.start_inspection(player)
    services.start_solve(player)
    services.stop_solve(player, time_ms)


@pytest.fixture
def ann(add_player):
    return add_player("Ann")


def test_an_unknown_challenge_is_not_found(admin):
    assert admin.get("/admin/challenges/nope").status_code == 404


def test_shows_the_challenge_code_status_and_players_with_the_owner_marked(
    admin, challenge, add_player
):
    add_player("Ann")

    html = admin.get(f"/admin/challenges/{challenge.slug}").data.decode()

    assert challenge.slug in html
    assert "Waiting" in html
    assert re.search(r'<li class="player player-co">\s*Tom \(owner\)', html)
    assert re.search(r'<li class="player">\s*Ann', html)


def test_shows_when_the_challenge_started_and_when_players_joined_in_uk_time(admin, clock, db):
    clock.now = datetime(2026, 7, 15, 9, 5, tzinfo=UTC)
    challenge = services.create_challenge("Tom", "cookie-tom")
    clock.advance(minutes=3)
    services.join_challenge(challenge, "Ann", "cookie-ann")

    html = admin.get(f"/admin/challenges/{challenge.slug}").data.decode()

    assert "15 Jul 2026, 10:05" in html
    assert re.search(r"Ann.*joined 15 Jul 2026, 10:08", html, re.S)


def test_says_so_when_no_rounds_were_played(admin, challenge):
    assert b"No rounds played" in admin.get(f"/admin/challenges/{challenge.slug}").data


def test_shows_each_round_with_its_puzzle_scramble_and_picture(admin, challenge, co):
    services.start_round(challenge, co, "333")
    services.complete_round(challenge)
    services.start_round(challenge, co, "pyram")

    html = admin.get(f"/admin/challenges/{challenge.slug}").data.decode()

    first, second = html.index("Round 1"), html.index("Round 2")
    assert first < second
    assert "Round 1: 3x3" in html
    assert "Round 2: Pyraminx" in html
    assert "R U R&#39; U&#39; 1" in html[first:second]
    assert f'src="/c/{challenge.slug}/rounds/1/scramble.svg"' in html[first:second]
    assert "R U R&#39; U&#39; 2" in html[second:]
    assert f'src="/c/{challenge.slug}/rounds/2/scramble.svg"' in html[second:]


def test_shows_each_rounds_results_ranked_with_times_and_dnfs(
    admin, challenge, co, ann, add_player
):
    bob = add_player("Bob")
    services.start_round(challenge, co)
    finish(ann, 65_430)
    finish(co, 9_870)
    services.start_inspection(bob)
    services.inspection_expired(bob)

    html = admin.get(f"/admin/challenges/{challenge.slug}").data

    assert results(html) == ["1st Tom 9.87", "2nd Ann 1:05.43", "3rd Bob DNF"]


def test_a_round_still_in_progress_leaves_out_unfinished_solves(admin, challenge, co, ann):
    services.start_round(challenge, co)
    finish(ann, 12_000)
    services.start_inspection(co)

    html = admin.get(f"/admin/challenges/{challenge.slug}").data

    assert results(html) == ["1st Ann 12.00"]


def test_a_round_with_no_results_says_so(admin, challenge, co):
    services.start_round(challenge, co)

    assert b"No results" in admin.get(f"/admin/challenges/{challenge.slug}").data


def test_links_back_to_the_list(admin, challenge):
    assert b'href="/admin"' in admin.get(f"/admin/challenges/{challenge.slug}").data


@pytest.mark.parametrize(
    ("time_ms", "shown"),
    [
        (None, "DNF"),
        (9_870, "9.87"),
        (12_345, "12.34"),  # truncated to hundredths, like WCA results: no rounding
        (12_349, "12.34"),
        (59_999, "59.99"),
        (60_009, "1:00.00"),
        (65_430, "1:05.43"),
        (600_000, "10:00.00"),
    ],
)
def test_solve_times_are_shown_like_the_live_results(time_ms, shown):
    from app.admin import solve_time

    assert solve_time(time_ms) == shown
