import uuid

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import Challenge, ChallengeStatus, Player, Round, RoundStatus, Solve, SolveResult


def make_challenge(db, slug="abc123", cookie_id="cookie-co"):
    challenge = Challenge(slug=slug)
    co = Player(challenge=challenge, cookie_id=cookie_id, display_name="Tom", is_co=True)
    challenge.co_player = co
    db.session.add(challenge)
    db.session.commit()
    return challenge


def make_round(db, challenge, round_number=1):
    rnd = Round(
        challenge=challenge,
        round_number=round_number,
        puzzle="333",
        scramble_text="R U R' U'",
        scramble_svg="<svg/>",
    )
    db.session.add(rnd)
    db.session.commit()
    return rnd


def test_new_challenge_has_uuid_id_waiting_status_and_its_co(db):
    challenge = make_challenge(db)

    assert challenge.id is not None
    assert challenge.status == ChallengeStatus.WAITING
    assert challenge.current_round is None
    assert challenge.created_at is not None
    assert challenge.co_player.is_co is True
    assert challenge.co_player.challenge_id == challenge.id


def test_new_player_starts_disconnected_with_join_time(db):
    challenge = make_challenge(db)
    player = challenge.co_player

    assert player.connected is False
    assert player.joined_at is not None


def test_challenge_slug_is_unique(db):
    make_challenge(db, slug="same")

    with pytest.raises(IntegrityError):
        make_challenge(db, slug="same", cookie_id="other")


def test_cookie_id_is_unique_within_a_challenge(db):
    challenge = make_challenge(db, cookie_id="dup")
    db.session.add(Player(challenge=challenge, cookie_id="dup", display_name="Twin"))

    with pytest.raises(IntegrityError):
        db.session.commit()


def test_same_cookie_can_join_different_challenges(db):
    make_challenge(db, slug="one", cookie_id="dup")
    make_challenge(db, slug="two", cookie_id="dup")

    assert Player.query.filter_by(cookie_id="dup").count() == 2


def test_new_round_is_active_and_can_be_the_current_round(db):
    challenge = make_challenge(db)
    rnd = make_round(db, challenge)
    challenge.current_round = rnd
    db.session.commit()

    assert rnd.status == RoundStatus.ACTIVE
    assert rnd.ended_at is None
    assert rnd.started_at is not None
    assert challenge.current_round.id == rnd.id


def test_round_number_is_unique_within_a_challenge(db):
    challenge = make_challenge(db)
    make_round(db, challenge, round_number=1)

    with pytest.raises(IntegrityError):
        make_round(db, challenge, round_number=1)


def test_new_solve_is_in_progress_until_it_has_a_result(db):
    challenge = make_challenge(db)
    rnd = make_round(db, challenge)
    solve = Solve(round=rnd, player=challenge.co_player)
    db.session.add(solve)
    db.session.commit()

    assert solve.result is None
    assert solve.time_ms is None


def test_one_solve_per_player_per_round(db):
    challenge = make_challenge(db)
    rnd = make_round(db, challenge)
    db.session.add(Solve(round=rnd, player=challenge.co_player))
    db.session.commit()
    db.session.add(Solve(round=rnd, player=challenge.co_player))

    with pytest.raises(IntegrityError):
        db.session.commit()


def test_solve_result_values_match_spec():
    assert {r.value for r in SolveResult} == {"ok", "dnf"}
    # "ended" is our addition to SPEC.md, for a challenge whose CO has gone for good.
    assert {s.value for s in ChallengeStatus} == {
        "waiting",
        "round_active",
        "round_results",
        "ended",
    }
    assert {s.value for s in RoundStatus} == {"active", "complete"}


def test_foreign_keys_are_enforced(db):
    db.session.add(Player(challenge_id=uuid.uuid4(), cookie_id="c", display_name="Ghost"))

    with pytest.raises(IntegrityError):
        db.session.commit()
