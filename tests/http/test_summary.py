import re

import pytest

from app import services
from app.models import ChallengeStatus, Player


def rows(html: str, css_class: str) -> list[str]:
    """Each <li class="css_class ..."> row's text, tags stripped."""
    found = re.findall(rf'<li class="{css_class}[^"]*">(.*?)</li>', html, re.S)
    return [" ".join(re.sub(r"<[^>]+>", " ", row).split()) for row in found]


def finish(player, time_ms):
    services.start_inspection(player)
    services.start_solve(player)
    services.stop_solve(player, time_ms)


def end_challenge(app, challenge, clock):
    """The owner leaves and doesn't come back within the grace period."""
    services.player_left(challenge.co_player)
    clock.advance(seconds=app.config["CO_GRACE_SECONDS"])
    services.end_abandoned_challenges()


@pytest.fixture
def played(app, challenge, co, add_player, clock):
    """Two rounds: Amy wins a 3x3 round, then Tom wins a 2x2 round; then the owner leaves."""
    amy = add_player("Amy")
    services.start_round(challenge, co, puzzle="333")
    finish(co, 12_345)
    finish(amy, 9_870)
    services.start_round(challenge, co, puzzle="222")
    finish(co, 4_010)
    finish(amy, 5_500)
    end_challenge(app, challenge, clock)
    return challenge


def summary_url(challenge):
    return f"/c/{challenge.slug}/summary"


def test_an_unknown_challenge_has_no_summary(client):
    assert client.get("/c/nope/summary").status_code == 404


def test_a_challenge_still_going_sends_the_summary_back_to_the_game(client, challenge):
    response = client.get(summary_url(challenge))

    assert response.status_code == 302
    assert response.headers["Location"] == f"/c/{challenge.slug}"


def test_the_summary_opens_by_saying_the_challenge_has_ended(client, played):
    html = client.get(summary_url(played)).data.decode()

    assert "This challenge has ended" in html
    assert html.index("This challenge has ended") < html.index("Final standings")


def test_the_summary_shows_the_final_standings_by_points(client, played):
    html = client.get(summary_url(played)).data.decode()

    assert rows(html, "standing") == ["1st Amy (1)", "1st Tom (1)"]


def test_the_summary_shows_each_round_with_its_puzzle_scramble_and_results(client, played):
    html = client.get(summary_url(played)).data.decode()

    assert html.index("Round 1: 3x3") < html.index("Round 2: 2x2")
    assert "R U R&#39; U&#39; 1" in html
    assert f'src="/c/{played.slug}/rounds/2/scramble.svg"' in html
    assert rows(html, "result") == [
        "1st Amy (1) 9.87",
        "2nd Tom (1) 12.34",
        "1st Tom (1) 4.01",
        "2nd Amy (1) 5.50",
    ]


def test_a_challenge_with_no_rounds_says_so(app, client, challenge, clock):
    end_challenge(app, challenge, clock)

    html = client.get(summary_url(challenge)).data.decode()

    assert "No rounds were played." in html
    assert rows(html, "standing") == ["1st Tom (0)"]


def test_the_summary_offers_a_new_challenge(client, played):
    html = client.get(summary_url(played)).data.decode()

    assert re.search(r'<a [^>]*href="/"[^>]*>Start a new challenge</a>', html)


def test_a_player_opening_an_ended_challenge_goes_to_its_summary(client, played):
    client.post(f"/c/{played.slug}/join", data={"display_name": "Amy"})

    response = client.get(f"/c/{played.slug}")

    assert response.status_code == 302
    assert response.headers["Location"] == summary_url(played)


def test_a_stranger_opening_an_ended_challenge_goes_to_its_summary(app, played):
    response = app.test_client().get(f"/c/{played.slug}")

    assert response.headers["Location"] == summary_url(played)


def test_joining_an_ended_challenge_goes_to_its_summary_without_adding_a_player(app, db, played):
    response = app.test_client().post(f"/c/{played.slug}/join", data={"display_name": "Bob"})

    assert response.headers["Location"] == summary_url(played)
    assert db.session.scalar(db.select(Player).filter_by(display_name="Bob")) is None


def test_the_summary_depends_only_on_the_challenge_having_ended_not_on_why(client, db, challenge):
    # A future manual "End challenge" should get the same page as the owner leaving.
    challenge.status = ChallengeStatus.ENDED
    db.session.commit()

    response = client.get(summary_url(challenge))

    assert response.status_code == 200
    assert "This challenge has ended" in response.data.decode()
    assert "owner left" not in response.data.decode()
