from app import services


def finish(player, time_ms):
    services.start_inspection(player)
    services.start_solve(player)
    services.stop_solve(player, time_ms=time_ms)


def points_by_name(challenge):
    points = services.points(challenge)
    return {p.display_name: points[p.id] for p in challenge.players}


def test_everyone_starts_on_zero_points(challenge, add_player):
    add_player("Amy")

    assert points_by_name(challenge) == {"Tom": 0, "Amy": 0}


def test_winning_a_round_is_worth_one_point(challenge, co, add_player):
    amy = add_player("Amy")
    services.start_round(challenge, co)
    finish(co, 12_000)
    finish(amy, 9_000)

    assert points_by_name(challenge) == {"Tom": 0, "Amy": 1}


def test_points_add_up_across_rounds(challenge, co, add_player):
    amy = add_player("Amy")
    for tom_ms, amy_ms in ((12_000, 9_000), (8_000, 9_000), (7_000, 9_000)):
        services.start_round(challenge, co)
        finish(co, tom_ms)
        finish(amy, amy_ms)

    assert points_by_name(challenge) == {"Tom": 2, "Amy": 1}


def test_players_tied_for_first_each_get_a_point(challenge, co, add_player):
    amy = add_player("Amy")
    services.start_round(challenge, co)
    finish(co, 9_001)
    finish(amy, 9_009)  # both 9.00 once truncated to hundredths

    assert points_by_name(challenge) == {"Tom": 1, "Amy": 1}


def test_a_round_where_everyone_dnfs_awards_no_point(challenge, co, add_player):
    add_player("Amy")
    services.start_round(challenge, co)
    services.end_round(challenge, co)

    assert points_by_name(challenge) == {"Tom": 0, "Amy": 0}


def test_the_round_in_progress_scores_nothing_until_it_ends(challenge, co, add_player):
    add_player("Amy")
    services.start_round(challenge, co)
    finish(co, 9_000)

    assert points_by_name(challenge) == {"Tom": 0, "Amy": 0}

    services.end_round(challenge, co)

    assert points_by_name(challenge) == {"Tom": 1, "Amy": 0}


def standings_rows(challenge):
    return [
        (row["position"], row["display_name"], row["points"])
        for row in services.standings(challenge)
    ]


def test_standings_rank_everyone_by_points_most_first(challenge, co, add_player):
    amy = add_player("Amy")
    add_player("Bob")
    for tom_ms, amy_ms in ((12_000, 9_000), (8_000, 9_000), (7_000, 9_000)):
        services.start_round(challenge, co)
        finish(co, tom_ms)
        finish(amy, amy_ms)
        services.end_round(challenge, co)

    assert standings_rows(challenge) == [(1, "Tom", 2), (2, "Amy", 1), (3, "Bob", 0)]


def test_standings_share_a_position_on_equal_points_and_list_ties_alphabetically(
    challenge, add_player
):
    add_player("bea")
    add_player("Amy")

    assert standings_rows(challenge) == [(1, "Amy", 0), (1, "bea", 0), (1, "Tom", 0)]


def test_standings_after_a_tie_skip_the_shared_places(challenge, co, add_player):
    amy = add_player("Amy")
    add_player("Bob")
    services.start_round(challenge, co)
    finish(co, 9_001)
    finish(amy, 9_009)
    services.end_round(challenge, co)

    assert standings_rows(challenge) == [(1, "Amy", 1), (1, "Tom", 1), (3, "Bob", 0)]
