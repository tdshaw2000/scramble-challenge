"""A player marks their own solve as +2 or DNF from the results list. Both are toggles:
tap to turn on, tap again to turn off. Only their own row has them."""

from playwright.sync_api import expect

from tests.e2e.test_game import (
    advance,
    leaderboard,
    solve,
    tom_and_amy,  # noqa: F401  (fixture)
)


def own_row(page, name):
    return page.locator("#result-list li", has_text=name)


def test_only_your_own_row_has_the_toggles(tom_and_amy):  # noqa: F811
    tom, amy, _ = tom_and_amy
    tom.get_by_role("button", name="Start round").click()

    solve(amy, 12_345)

    row = own_row(amy, "Amy")
    expect(row.get_by_role("button", name="+2")).to_be_visible()
    expect(row.get_by_role("button", name="DNF")).to_be_visible()
    expect(row.get_by_role("button", name="+2")).to_have_attribute("aria-pressed", "false")
    solve(tom, 13_000)
    expect(own_row(tom, "Amy")).to_be_visible()
    expect(own_row(tom, "Amy").get_by_role("button")).to_have_count(0)
    expect(own_row(tom, "Tom").get_by_role("button")).to_have_count(2)
    expect(own_row(amy, "Tom").get_by_role("button")).to_have_count(0)


def test_plus_two_toggles_on_and_off_for_everyone(tom_and_amy):  # noqa: F811
    tom, amy, _ = tom_and_amy
    tom.get_by_role("button", name="Start round").click()
    solve(amy, 12_345)
    plus_two = own_row(amy, "Amy").get_by_role("button", name="+2")

    plus_two.click()

    expect(plus_two).to_have_attribute("aria-pressed", "true")
    for page in (tom, amy):
        expect(own_row(page, "Amy").locator(".time")).to_have_text("14.34+")

    plus_two.click()

    expect(plus_two).to_have_attribute("aria-pressed", "false")
    for page in (tom, amy):
        expect(own_row(page, "Amy").locator(".time")).to_have_text("12.34")


def test_dnf_toggles_and_turning_it_off_brings_the_time_back(tom_and_amy):  # noqa: F811
    tom, amy, _ = tom_and_amy
    tom.get_by_role("button", name="Start round").click()
    solve(amy, 12_345)
    row = own_row(amy, "Amy")
    row.get_by_role("button", name="+2").click()
    expect(row.locator(".time")).to_have_text("14.34+")

    row.get_by_role("button", name="DNF").click()

    expect(row.get_by_role("button", name="DNF")).to_have_attribute("aria-pressed", "true")
    expect(row.get_by_role("button", name="+2")).to_be_disabled()
    for page in (tom, amy):
        expect(own_row(page, "Amy").locator(".time")).to_have_text("DNF")

    row.get_by_role("button", name="DNF").click()

    expect(row.get_by_role("button", name="+2")).to_be_enabled()
    for page in (tom, amy):
        expect(own_row(page, "Amy").locator(".time")).to_have_text("14.34+")


def test_a_plus_two_from_inspection_starts_switched_on(tom_and_amy):  # noqa: F811
    tom, amy, _ = tom_and_amy
    tom.get_by_role("button", name="Start round").click()
    amy.get_by_role("button", name="Start inspection").click()
    advance(amy, 16_000)
    amy.locator("#overlay").click()  # start solving, into the +2
    advance(amy, 10_000)
    amy.locator("#overlay").click()  # stop

    plus_two = own_row(amy, "Amy").get_by_role("button", name="+2")
    expect(plus_two).to_have_attribute("aria-pressed", "true")
    plus_two.click()

    expect(own_row(tom, "Amy").locator(".time")).to_have_text("10.00")


def test_a_dnf_from_inspection_running_out_has_no_toggles(tom_and_amy):  # noqa: F811
    tom, amy, _ = tom_and_amy
    tom.get_by_role("button", name="Start round").click()
    amy.get_by_role("button", name="Start inspection").click()

    advance(amy, 17_000)

    expect(own_row(amy, "Amy")).to_contain_text("DNF")
    expect(amy.locator("#result-list").get_by_role("button")).to_have_count(0)


def test_a_dnf_on_the_results_screen_moves_the_round_point(tom_and_amy):  # noqa: F811
    tom, amy, _ = tom_and_amy
    tom.get_by_role("button", name="Start round").click()
    solve(amy, 9_000)
    solve(tom, 12_000)
    for page in (tom, amy):
        expect(page.locator("#results-heading")).to_have_text("Round 1 results")
    assert leaderboard(tom) == [["1st", "Amy (1)", "9.00"], ["2nd", "Tom (0)", "12.00"]]

    own_row(amy, "Amy").get_by_role("button", name="DNF").click()

    for page in (tom, amy):
        expect(own_row(page, "Amy").locator(".time")).to_have_text("DNF")
        expect(page.locator("#players")).to_contain_text("Tom (1)")
    assert leaderboard(tom) == [["1st", "Tom (1)", "12.00"], ["2nd", "Amy (0)", "DNF"]]


def test_the_toggles_go_once_the_next_round_starts(tom_and_amy):  # noqa: F811
    tom, amy, _ = tom_and_amy
    tom.get_by_role("button", name="Start round").click()
    solve(amy, 9_000)
    solve(tom, 12_000)
    expect(own_row(amy, "Amy").get_by_role("button", name="DNF")).to_be_visible()

    tom.get_by_role("button", name="Start round").click()

    expect(amy.get_by_role("heading", name="Round 2")).to_be_visible()
    expect(amy.locator("#result-list").get_by_role("button")).to_have_count(0)
