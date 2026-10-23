#!/bin/bash
# docker compose for the live stack, from anywhere: e.g. scripts/compose.sh logs web --tail 30
# Compose otherwise names the stack after the checkout's folder ("repo") and starts a
# second, empty stack beside the live one. Use this instead of plain docker compose.
set -euo pipefail
cd "$(dirname "$0")/.."
export COMPOSE_PROJECT_NAME="scramble-challenge"
exec docker compose "$@"
