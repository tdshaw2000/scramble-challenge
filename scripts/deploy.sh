#!/bin/bash
# Runs on the server, not in GitHub Actions. It's exec'd by scripts/deploy-launcher.sh
# once that has already brought this checkout up to date with origin/main — deploy.sh
# itself never touches its own checkout (see deploy-launcher.sh for why).
#
# Pulls the new images, snapshots and restarts the Docker Compose stack, and smoke
# tests the result — the same steps the old self-hosted-runner deploy job used to run.
set -euo pipefail
cd "$(dirname "$0")/.."

# Compose otherwise names the stack after this directory ("repo"), which would start a
# second stack alongside the live one instead of updating it. Pin it to what the stack
# has always been called, independent of where the checkout happens to live.
export COMPOSE_PROJECT_NAME="scramble-challenge"

trap 'docker compose logs --tail 100' ERR

echo "== Pulling the new images =="
docker compose pull

echo "== Snapshotting the database before restarting =="
docker compose run --rm --no-deps backup python -m app.backup snapshot predeploy

echo "== Making sure the shared edge network exists =="
docker network inspect scramble-challenge-edge > /dev/null 2>&1 \
  || docker network create scramble-challenge-edge

echo "== Restarting the stack =="
export SITE_ADDRESS=scramble-challenge.duckdns.org
export WCA_SITE_ADDRESS=wca-records-analyser.duckdns.org
docker compose up -d --remove-orphans

echo "== Smoke testing the live site =="
scripts/smoke-test.sh

docker image prune -f
