# Scramble Challenge

A live multiplayer scramble-timing party game for speedcubers. See [SPEC.md](SPEC.md).

## Development

```bash
uv sync                 # install dependencies into .venv
uv run playwright install chromium   # once, for the browser tests
uv run pytest           # all tests, browser tests included, with coverage
uv run pytest -m tnoodle  # the one test that needs a real TNoodle server
uv run ruff check . && uv run ruff format --check .
```

## Docker

```bash
docker compose build
docker compose up -d          # web on port 5000 (override with WEB_PORT)
scripts/smoke-test.sh         # checks /healthz and a TNoodle scramble + SVG
docker compose down
```

The SQLite database lives on the `data` volume; migrations run when the web container starts.

## Changing the look

All styling lives in `app/static/themes/<name>/theme.css`. Templates and
`challenge.js` carry no styling (tests enforce this). Pick a theme with `THEME`
in `app/config.py`: `mario64` (default) or `plain`. To add one, copy a theme
folder and edit its CSS.
