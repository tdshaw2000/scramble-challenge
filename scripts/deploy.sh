#!/bin/bash
# Runs on the server, not in GitHub Actions. It's invoked remotely over SSH by the
# "deploy" job in .github/workflows/ci.yml, using a key that server-setup.sh restricts
# to always running exactly this script (see the "command=" entry it adds to
# authorized_keys) — so whatever that job asks for, this is the only thing that runs.
#
# It updates this checkout to the latest main, then pulls, snapshots and restarts the
# Docker Compose stack, the same way the old self-hosted-runner deploy job used to.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "== Updating the checkout =="
git fetch --depth 1 origin main
git reset --hard origin/main

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
