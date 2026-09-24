# Scramble Challenge

A live multiplayer scramble-timing party game for speedcubers. See [SPEC.md](SPEC.md).

## Development

```bash
uv sync                 # install dependencies into .venv
uv run pytest           # tests with coverage
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
