"""Pure game rules from SPEC.md: no Flask, no database."""

from collections.abc import Iterable, Sequence
from typing import Protocol

# TNoodle event codes and the names players see: the WCA puzzles, without the
# blindfolded, fewest-moves and fast-generation variants.
PUZZLE_NAMES = {
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

DEFAULT_PUZZLE = "333"


class Rankable(Protocol):
    name: str
    time_ms: int | None  # None means DNF


def rank[R: Rankable](entries: Sequence[R]) -> list[tuple[int, R]]:
    """Fastest first; equal times share a position (1, 1, 3); DNFs last, sharing one position."""
    ordered = sorted(
        entries,
        key=lambda e: (e.time_ms is None, e.time_ms or 0, e.name.casefold()),
    )
    ranked: list[tuple[int, R]] = []
    for index, entry in enumerate(ordered):
        if index and entry.time_ms == ordered[index - 1].time_ms:
            position = ranked[-1][0]
        else:
            position = index + 1
        ranked.append((position, entry))
    return ranked


def default_puzzle(previous_puzzle: str | None) -> str:
    return previous_puzzle or DEFAULT_PUZZLE


def round_is_over(connected: Iterable[str], finished: Iterable[str]) -> bool:
    return set(connected) <= set(finished)
