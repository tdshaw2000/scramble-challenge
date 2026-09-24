from datetime import UTC, datetime, timedelta

from app.tnoodle import Scramble, TNoodleError


class FakeTNoodle:
    """Stands in for TNoodle: returns numbered scrambles and records what was asked for."""

    def __init__(self):
        self.requested: list[str] = []
        self.fail = False

    def generate(self, puzzle: str) -> Scramble:
        if self.fail:
            raise TNoodleError("fake TNoodle is down")
        self.requested.append(puzzle)
        n = len(self.requested)
        return Scramble(text=f"R U R' U' {n}", svg=f"<svg>{puzzle} {n}</svg>")


class FakeClock:
    """A clock the tests move by hand instead of waiting on real time."""

    def __init__(self, start: datetime = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)):
        self.now = start

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **kwargs) -> None:
        self.now += timedelta(**kwargs)
