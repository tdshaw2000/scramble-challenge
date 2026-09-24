import re

from playwright.sync_api import expect


def test_start_a_challenge_and_see_the_waiting_room(new_player):
    tom = new_player()
    tom.goto("/")

    tom.get_by_label("Your name").fill("Tom")
    tom.get_by_role("button", name="Start new challenge").click()

    expect(tom).to_have_url(re.compile(r"/c/[\w-]+$"))
    expect(tom.get_by_role("heading", name="Players")).to_be_visible()
    expect(tom.locator("#players")).to_contain_text("Tom")
    expect(tom.get_by_label("Share link")).to_have_value(re.compile(r"http://127\.0\.0\.1:\d+/c/"))
    expect(tom.get_by_role("button", name="Copy link")).to_be_visible()
    expect(tom.get_by_label("Puzzle")).to_have_value("333")
    expect(tom.get_by_role("button", name="Start round")).to_be_visible()
