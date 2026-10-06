# Standalone Caddy

The Caddy stack that fronts scramble-challenge and any other app sharing its
`scramble-challenge-edge` Docker network (wca-records-analyser today). Deliberately
its own Compose project — `name: caddy` in [`compose.yaml`](compose.yaml) — separate
from every app it fronts, so that redeploying any one app's own stack never restarts
this, and vice versa.

## One-time server setup

```bash
bash server-setup.sh
```

Opens ports 80 and 443 in the server's own firewall, creates the shared
`scramble-challenge-edge` network if it doesn't already exist (an app's own
`server-setup.sh` may have beaten it to this — both are idempotent), and copies
`compose.yaml` and `Caddyfile` to `~/apps/caddy/`.

Then, on the server:

```bash
cd ~/apps/caddy
cat > .env <<'EOF'
SCRCH_SITE_ADDRESS=scramble-challenge.duckdns.org
WCA_SITE_ADDRESS=wca-records-analyser.duckdns.org
EOF
docker compose up -d
```

## Deploying a change

There's no CI/CD for this stack — it changes rarely (mainly: a new app joining the
shared Caddy), so updates are manual. From this `edge/` directory on your own
machine:

- **`compose.yaml` changed**: copy it to `~/apps/caddy/compose.yaml` on the server,
  then `cd ~/apps/caddy && docker compose up -d`.
- **`Caddyfile` changed only**: copy it to `~/apps/caddy/Caddyfile`, then validate
  and reload rather than restart, so existing connections (including the other
  app's) aren't dropped. Run these from `~/apps/caddy` (`docker compose exec`
  finds the right container without needing to know its name):

  ```bash
  docker compose exec caddy caddy validate --config /etc/caddy/Caddyfile
  docker compose exec caddy caddy reload --config /etc/caddy/Caddyfile
  ```

## Migrating from Caddy running inside scramble-challenge's own stack

If `scramble-challenge_caddy_data` already holds live TLS certificates (Caddy used to
be part of scramble-challenge's own `docker-compose.yml`), point this stack's volume
at it instead of starting fresh, to avoid a Let's Encrypt reissue:

```yaml
volumes:
  caddy_data:
    external: true
    name: scramble-challenge_caddy_data
```

Revert that override once this stack has run with it at least once (Compose then owns
a volume of the same name under its own project).
