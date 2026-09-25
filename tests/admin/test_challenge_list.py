import re
from datetime import UTC, datetime

import pytest

from app import services
from app.extensions import db


def make_challenge(clock, owner="Tom", players=(), rounds=0):
    challenge = services.create_challenge(owner, f"cookie-{owner}-{clock.now}")
    for name in players:
        services.join_challenge(challenge, name, f"cookie-{name}-{clock.now}")
    for _ in range(rounds):
        services.start_round(challenge, challenge.co_player)
        services.complete_round(challenge)
    return challenge


def rows(html: bytes) -> list[str]:
    return re.findall(r'<tr class="admin-challenge">(.*?)</tr>', html.decode(), re.S)


@pytest.mark.parametrize("path", ["/admin", "/admin/challenges/abc"])
def test_every_admin_page_needs_a_login(client, path):
    response = client.get(path)

    assert response.status_code == 302
    assert response.headers["Location"] == "/admin/login"


def test_says_so_when_there_are_no_challenges(admin):
    assert b"No challenges yet" in admin.get("/admin").data


def test_lists_challenges_newest_first(admin, clock):
    make_challenge(clock, owner="Old")
    clock.advance(days=1)
    make_challenge(clock, owner="New")

    listed = rows(admin.get("/admin").data)

    assert len(listed) == 2
    assert "New" in listed[0]
    assert "Old" in listed[1]


def test_each_row_shows_code_owner_counts_and_status_and_links_to_the_challenge(admin, clock):
    challenge = make_challenge(clock, owner="Tom", players=["Ann", "Bob"], rounds=3)

    (row,) = rows(admin.get("/admin").data)

    assert f'href="/admin/challenges/{challenge.slug}"' in row
    assert challenge.slug in row
    assert "Tom" in row
    assert '<td class="admin-players">3</td>' in row  # the owner counts as a player
    assert '<td class="admin-rounds">3</td>' in row
    assert "Showing results" in row


def test_the_owner_is_shown_with_their_points(admin, clock):
    challenge = make_challenge(clock, owner="Tom")
    for _ in range(2):
        services.start_round(challenge, challenge.co_player)
        services.start_inspection(challenge.co_player)
        services.start_solve(challenge.co_player)
        services.stop_solve(challenge.co_player, 9_000)
        services.complete_round(challenge)

    (row,) = rows(admin.get("/admin").data)

    assert "<td>Tom (2)</td>" in row


@pytest.mark.parametrize(
    ("status", "label"),
    [
        ("waiting", "Waiting"),
        ("round_active", "Round in progress"),
        ("round_results", "Showing results"),
        ("ended", "Ended"),
    ],
)
def test_status_is_shown_in_words(admin, clock, status, label):
    challenge = make_challenge(clock)
    challenge.status = status
    db.session.commit()

    (row,) = rows(admin.get("/admin").data)

    assert label in row


def test_times_are_shown_in_uk_time(admin, clock):
    clock.now = datetime(2026, 1, 15, 9, 5, tzinfo=UTC)  # winter: UK time is UTC
    make_challenge(clock, owner="Winter")
    clock.now = datetime(2026, 7, 15, 9, 5, tzinfo=UTC)  # summer: UK time is UTC+1
    make_challenge(clock, owner="Summer")

    summer, winter = rows(admin.get("/admin").data)

    assert "15 Jan 2026, 09:05" in winter
    assert "15 Jul 2026, 10:05" in summer


def test_shows_fifty_challenges_a_page_with_a_link_to_older_ones(admin, clock):
    for n in range(51):
        clock.advance(minutes=1)
        make_challenge(clock, owner=f"P{n}")

    first = admin.get("/admin").data
    second = admin.get("/admin?page=2").data

    assert len(rows(first)) == 50
    assert b'href="/admin?page=2"' in first
    assert b"page=0" not in first  # no "newer" link on the first page
    (oldest,) = rows(second)
    assert "P0" in oldest
    assert b'href="/admin?page=1"' in second
    assert b"page=3" not in second


@pytest.mark.parametrize("page", ["0", "3", "abc"])
def test_a_page_that_does_not_exist_is_not_found(admin, clock, page):
    make_challenge(clock)

    assert admin.get(f"/admin?page={page}").status_code == 404


def test_names_are_escaped(admin, clock):
    make_challenge(clock, owner="<b>Eve</b>")

    html = admin.get("/admin").data

    assert b"<b>Eve</b>" not in html
    assert b"&lt;b&gt;Eve&lt;/b&gt;" in html
