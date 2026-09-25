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
docker compose up -d          # http://localhost via Caddy; web also on 127.0.0.1:5000
scripts/smoke-test.sh         # /healthz, a TNoodle scramble + SVG, and Caddy incl. WebSockets
docker compose down
```

The SQLite database lives on the `data` volume; migrations run when the web container starts.

## CI

`.github/workflows/ci.yml` runs on every pull request and every push to `main`:

- `test`: ruff, then every test, including the browser tests
- `tnoodle-contract`: the one test against a real TNoodle (`pytest -m tnoodle`)
- `smoke`: builds the Docker Compose stack and runs `scripts/smoke-test.sh`
- `publish` (on `main` only, after the three above pass): builds the `web` and
  `tnoodle` images for amd64 and arm64 and pushes them to GHCR. TNoodle is built
  once per version, so change `TNOODLE_VERSION` in the workflow and in
  `docker-compose.yml` together.
- `deploy` (on `main` only, after `publish`): runs on the OCI server's own runner
  (label `oci`). It pulls the new images, restarts the stack, and runs the smoke test
  against https://scramble-challenge.duckdns.org.

## Deploying (one-time server setup)

The live site runs on an OCI Ampere server (Ubuntu 24.04). Caddy serves it over HTTPS
and gets its certificate from Let's Encrypt automatically.

1. Point scramble-challenge.duckdns.org at the server's public IP (duckdns.org), and
   allow TCP 80 and 443 in the subnet's security list (OCI console).
2. Get a runner token: GitHub repo, Settings > Actions > Runners > New self-hosted
   runner. Copy the value after `--token` (single-use, expires in an hour).
3. Put `scripts/server-setup.sh` on the server, either with
   `scp -i <key> scripts/server-setup.sh ubuntu@<ip>:` or by pasting the file into
   `nano server-setup.sh` over SSH.
4. On the server: `bash server-setup.sh <token>`. It opens ports 80 and 443 in the
   server's own firewall, installs Docker, and registers the runner as a service.
5. Re-run the latest CI run on `main` (or push to `main`). The `deploy` job does the rest.

## Admin area

`/admin` is a read-only view of every past challenge, its rounds and results, with
times in UK time. It is switched off (404) until a password is set on the server:

1. SSH to the server, then
   `cd ~/actions-runner/_work/scramble-challenge/scramble-challenge`.
2. `sudo python3 scripts/set_admin_password.py` asks for a password
   and writes its hash and a new secret key to `/etc/scramble-challenge/admin.env`.
3. Re-run the latest CI run on `main` so the deploy restarts the web container with it.

Run it again to change the password; that also logs out every admin browser.

## Changing the look

All styling lives in `app/static/themes/<name>/theme.css`. Templates and
`challenge.js` carry no styling (tests enforce this). Pick a theme with `THEME`
in `app/config.py`: `mario64` (default) or `plain`. To add one, copy a theme
folder and edit its CSS.
