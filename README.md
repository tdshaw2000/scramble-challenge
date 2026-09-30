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
- `deploy` (on `main` only, after `publish`): runs on a normal GitHub-hosted runner
  and SSHes into the server to trigger `scripts/deploy.sh`, which pulls the new
  images, takes a `predeploy` snapshot of the database, restarts the stack, and runs
  the smoke test against https://scramble-challenge.duckdns.org. There's no
  self-hosted runner: the SSH key is restricted, server-side, to running nothing but
  that one script, so it's safe to keep as a secret even with the repo public.

## Deploying (one-time server setup)

The live site runs on an OCI Ampere server (Ubuntu 24.04). Caddy serves it over HTTPS
and gets its certificate from Let's Encrypt automatically.

1. Point scramble-challenge.duckdns.org at the server's public IP (duckdns.org), and
   allow TCP 80 and 443 in the subnet's security list (OCI console).
2. On your own machine, generate a dedicated deploy key (no passphrase, since GitHub
   Actions has to use it unattended): `ssh-keygen -t ed25519 -f deploy_key -N ""`.
3. Put `scripts/server-setup.sh` on the server, either with
   `scp -i <key> scripts/server-setup.sh ubuntu@<ip>:` or by pasting the file into
   `nano server-setup.sh` over SSH. It needs `scripts/deploy-launcher.sh` from the same
   checkout too, or `scp` both.
4. On the server: `bash server-setup.sh "$(cat deploy_key.pub)"`. It opens ports 80
   and 443 in the server's own firewall, installs Docker, clones this repo for
   deploys, installs `deploy-launcher.sh` at `$HOME` (deliberately outside that
   checkout — it's what git-updates the checkout, so it can't safely live inside it),
   and restricts the public key, in `authorized_keys`, to always running that launcher
   — nothing else, whatever command is sent over it. It also asks for a GHCR token to
   `docker login` with, needed only while the `web`/`tnoodle` packages are private;
   leave it blank once you've made them public (Settings on the package itself, or
   Package settings > Manage Actions access, once the repo is public too).
5. In the repo's GitHub settings (Settings > Secrets and variables > Actions), add:
   - `DEPLOY_HOST`: the server's IP or hostname.
   - `DEPLOY_SSH_KEY`: the contents of `deploy_key` (the *private* half). Delete the
     local copies of both files once it's saved.
6. Re-run the latest CI run on `main` (or push to `main`). The `deploy` job SSHes in,
   which runs the launcher, which brings the checkout up to date and hands off to
   `scripts/deploy.sh` to do the rest.

Re-running `server-setup.sh` (a new deploy key, a fresh server) is safe: cloning the
repo and adding the key are both skipped if already done.

## A second app behind the same Caddy

Caddy joins an external Docker network, `scramble-challenge-edge`, created once by
`scripts/server-setup.sh` (and by CI, for the smoke test). Another app's own
`docker-compose.yml`, running as its own separate project on the same server, can
share this site's HTTPS by joining the same network and giving its service a name
Caddy can proxy to:

```yaml
services:
  wca-records-analyser:
    # ...
    networks:
      - default
      - scramble-challenge-edge

networks:
  scramble-challenge-edge:
    external: true
```

Then add a site block to `docker/caddy/Caddyfile` for it, following the
`WCA_SITE_ADDRESS` block as a template: gate the real domain behind an env var that
defaults to a bare port (never a live domain), so CI and local `docker compose up`
never attempt a Let's Encrypt challenge they can't complete, and set the real domain
as that variable only in the `deploy` job's `env` in `.github/workflows/ci.yml`.

## Admin area

`/admin` is a read-only view of every past challenge, its rounds and results, with
times in UK time. It is switched off (404) until a password is set on the server:

1. SSH to the server, then
   `cd ~/scramble-challenge`.
2. `sudo python3 scripts/set_admin_password.py` asks for a password
   and writes its hash and a new secret key to `/etc/scramble-challenge/admin.env`.
3. Re-run the latest CI run on `main` so the deploy restarts the web container with it.

Run it again to change the password; that also logs out every admin browser.

## Database backups

The `backup` service (`app/backup.py`) keeps snapshots of the SQLite database on the
`backups` volume, on the server itself. They are not copied anywhere else.

- `predeploy-<UTC time>.db`: taken by every deploy, just before the restart.
- `nightly-<UTC time>.db`: taken every night at 03:00 UK time.
- `prerestore-<UTC time>.db`: the database as it was just before a restore.

Each kind keeps its newest 14. Snapshots use SQLite's online backup, so they are safe
to take while people are playing.

To put a snapshot back (for example, after a deploy broke the data), SSH to the server
and run these from `~/scramble-challenge`:

```bash
docker compose run --rm --no-deps backup python -m app.backup list    # newest first
docker compose stop web                                                # nobody writes meanwhile
docker compose run --rm --no-deps backup python -m app.backup restore <name>.db
docker compose start web
```

`restore` first saves the current database as a `prerestore` snapshot, so a restore
can itself be undone the same way. Players in a game at that moment will need to
reload the page. A restore brings back data only: if the broken deploy also changed
the database schema, revert that change on `main` too, or the next deploy will
migrate the restored data forward again.

## Changing the look

All styling lives in `app/static/themes/<name>/theme.css`. Templates and
`challenge.js` carry no styling (tests enforce this). Pick a theme with `THEME`
in `app/config.py`: `mario64` (default) or `plain`. To add one, copy a theme
folder and edit its CSS.
