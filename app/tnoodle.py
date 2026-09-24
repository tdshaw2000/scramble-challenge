"""Client for TNoodle, the WCA scramble generator, over its local HTTP API."""

from dataclasses import dataclass

import requests

TIMEOUT_SECONDS = 10


@dataclass(frozen=True)
class Scramble:
    text: str
    svg: str


class TNoodleError(Exception):
    pass


class TNoodleClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    def generate(self, puzzle: str) -> Scramble:
        text = self._get(f"/api/v0/scramble/{puzzle}").json()[0]
        svg = self._get(f"/api/v0/view/{puzzle}/svg", params={"scramble": text}).text
        return Scramble(text=text, svg=svg)

    def _get(self, path: str, params: dict | None = None) -> requests.Response:
        try:
            response = requests.get(
                f"{self.base_url}{path}", params=params, timeout=TIMEOUT_SECONDS
            )
            response.raise_for_status()
        except requests.RequestException as error:
            raise TNoodleError(f"TNoodle request to {path} failed: {error}") from error
        return response
