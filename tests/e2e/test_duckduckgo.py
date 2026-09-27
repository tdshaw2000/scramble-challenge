"""The DuckDuckGo browser hides elements that look like ads, going by their ids and classes.
It hides "hide" matches outright, and "hide-empty" and "closest-empty" matches when they are
empty as the page loads, which is how it hid the empty round results list (#leaderboard).
These tests apply its rules in Chromium, so a name that clashes with them fails here."""

import json
from pathlib import Path

from playwright.sync_api import expect

from tests.e2e.test_game import FAKE_NOW, advance, join, set_now, solve, start_challenge

RULES_FILE = Path(__file__).parent / "fixtures" / "ddg_hiding_rules.txt"
RULES = [
    line.split(" ", 1)
    for line in RULES_FILE.read_text().splitlines()
    if line and not line.startswith("#")
]

# A simplified copy of what DuckDuckGo does: run the rules once the page has loaded, and
# again a little later, hiding what matches. Hidden elements stay hidden.
DUCKDUCKGO_HIDING = """
  const rules = window.__duckduckgoRules;
  const isEmpty = (el) => el.textContent.trim() === "" && !el.querySelector("img, svg, iframe");
  const hideMatches = () => {
    for (const [type, selector] of rules) {
      let matches;
      try { matches = document.querySelectorAll(selector); } catch { continue; }
      for (const el of matches) {
        if (type === "hide" || isEmpty(el)) {
          el.style.setProperty("display", "none", "important");
          el.dataset.hiddenByDuckduckgo = "";
        }
      }
    }
  };
  document.addEventListener("DOMContentLoaded", () => {
    hideMatches();
    setTimeout(hideMatches, 300);
  });
"""


def duckduckgo_player(new_player):
    page = new_player()
    page.add_init_script(FAKE_NOW)
    page.add_init_script(f"window.__duckduckgoRules = {json.dumps(RULES)};")
    page.add_init_script(DUCKDUCKGO_HIDING)
    return page


def test_round_results_show_in_duckduckgo(new_player):
    tom, amy = duckduckgo_player(new_player), duckduckgo_player(new_player)
    link = start_challenge(tom)
    join(amy, link, "Amy")
    for page in (tom, amy):
        set_now(page, 1_000_000)
    tom.get_by_role("button", name="Start round").click()

    solve(amy, 12_340)
    solve(tom, 15_000)
    advance(tom, 0)

    for page in (tom, amy):
        expect(page.get_by_role("heading", name="Round 1 results")).to_be_visible()
        results = page.locator("#results li")
        expect(results).to_have_count(2)
        expect(results.first).to_be_visible()
        expect(results.first).to_contain_text("Amy")
        expect(page.locator("[data-hidden-by-duckduckgo]")).to_have_count(0)
