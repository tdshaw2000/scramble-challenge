from dataclasses import dataclass

from app.game import (
    DEFAULT_PUZZLE,
    PUZZLE_NAMES,
    default_puzzle,
    rank,
    round_is_over,
    round_winners,
)


@dataclass
class Entry:
    name: str
    time_ms: int | None  # None means DNF


def ranked(*entries):
    return [(position, entry.name) for position, entry in rank(list(entries))]


def test_rank_orders_fastest_first():
    assert ranked(Entry("slow", 20_000), Entry("fast", 9_000), Entry("mid", 12_000)) == [
        (1, "fast"),
        (2, "mid"),
        (3, "slow"),
    ]


def test_tied_times_share_a_position_and_the_next_position_is_skipped():
    result = ranked(Entry("a", 10_000), Entry("b", 10_000), Entry("c", 11_000))

    assert [position for position, _ in result] == [1, 1, 3]


def test_ties_further_down_also_skip():
    result = ranked(
        Entry("a", 9_000),
        Entry("b", 10_000),
        Entry("c", 10_000),
        Entry("d", 10_000),
        Entry("e", 12_000),
    )

    assert [position for position, _ in result] == [1, 2, 2, 2, 5]


def test_times_equal_to_the_hundredth_tie_like_wca():
    # WCA results drop everything past the hundredths, so 12.341 and 12.349 are both 12.34.
    result = ranked(Entry("b", 12_349), Entry("a", 12_341), Entry("c", 12_350))

    assert result == [(1, "a"), (1, "b"), (3, "c")]


def test_tied_entries_are_listed_alphabetically():
    assert ranked(Entry("zed", 10_000), Entry("amy", 10_000)) == [(1, "amy"), (1, "zed")]


def test_dnfs_come_after_every_timed_result_and_share_the_next_position():
    result = ranked(Entry("dnf1", None), Entry("a", 30_000), Entry("dnf2", None), Entry("b", 9_000))

    assert result == [(1, "b"), (2, "a"), (3, "dnf1"), (3, "dnf2")]


def test_all_dnf_all_share_first():
    assert ranked(Entry("a", None), Entry("b", None)) == [(1, "a"), (1, "b")]


def test_rank_of_nothing_is_empty():
    assert rank([]) == []


def test_first_round_defaults_to_3x3():
    assert DEFAULT_PUZZLE == "333"
    assert default_puzzle(previous_puzzle=None) == "333"


def test_puzzles_are_the_wca_puzzles_without_variants():
    assert list(PUZZLE_NAMES) == [
        "222", "333", "444", "555", "666", "777", "pyram", "skewb", "sq1", "minx", "clock",
    ]  # fmt: skip


def test_puzzles_have_names_people_recognise():
    assert PUZZLE_NAMES == {
        "222": "2x2",
        "333": "3x3",
        "444": "4x4",
        "555": "5x5",
        "666": "6x6",
        "777": "7x7",
        "pyram": "Pyraminx",
        "skewb": "Skewb",
        "sq1": "Square-1",
        "minx": "Megaminx",
        "clock": "Clock",
    }


def test_later_rounds_default_to_the_previous_rounds_puzzle():
    assert default_puzzle(previous_puzzle="222") == "222"


def test_round_is_over_when_every_connected_player_has_finished():
    assert round_is_over(connected={"a", "b"}, finished={"a", "b"}) is True


def test_round_is_not_over_while_a_connected_player_is_still_going():
    assert round_is_over(connected={"a", "b"}, finished={"a"}) is False


def test_finished_players_who_have_since_left_do_not_matter():
    assert round_is_over(connected={"a"}, finished={"a", "gone"}) is True


def winners(*entries):
    return {entry.name for entry in round_winners(list(entries))}


def test_the_fastest_player_wins_the_round():
    assert winners(Entry("slow", 20_000), Entry("fast", 9_000)) == {"fast"}


def test_players_tied_for_first_all_win():
    assert winners(Entry("a", 9_001), Entry("b", 9_009), Entry("c", 11_000)) == {"a", "b"}


def test_nobody_wins_a_round_where_everyone_dnfs():
    assert winners(Entry("a", None), Entry("b", None)) == set()


def test_nobody_wins_a_round_with_no_results():
    assert winners() == set()
