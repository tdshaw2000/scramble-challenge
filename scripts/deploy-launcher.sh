#!/bin/bash
# Installed by server-setup.sh at $HOME/deploy-launcher.sh — OUTSIDE the git checkout
# it updates. That matters: it's the forced command GitHub Actions' deploy key always
# runs (see the "command=" entry server-setup.sh adds to authorized_keys), and its own
# job is to git-update that checkout. A script that resets the hard way the very
# checkout it is itself currently being read from can be corrupted mid-run, so this
# file deliberately lives somewhere that reset can never touch, updates the checkout,
# and only then execs the (now current, freshly opened) scripts/deploy.sh.
set -euo pipefail

CHECKOUT_DIR="$HOME/scramble-challenge"
cd "$CHECKOUT_DIR"

git fetch --depth 1 origin main
git reset --hard origin/main

exec scripts/deploy.sh
