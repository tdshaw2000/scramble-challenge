#!/bin/bash
# One-time setup for the OCI server (Ubuntu 24.04, ARM). Run it on the server as the
# default "ubuntu" user:
#
#   bash server-setup.sh <deploy-public-key>
#
# <deploy-public-key> is the *public* half of the SSH key GitHub Actions uses to
# trigger deploys (see README.md "Deploying"). It's added to authorized_keys with a
# forced command, so that key can only ever run scripts/deploy.sh here, whatever
# command it's asked to run — safe to hand to a GitHub Actions secret even on a public
# repo, since a fork pull request never has access to that secret.
set -euo pipefail

DEPLOY_KEY="${1:?Usage: bash server-setup.sh <deploy-public-key>}"
REPO_URL="https://github.com/tdshaw2000/scramble-challenge"
# Everything for this app lives under its own folder, not loose in $HOME -- a second
# app set up the same way gets its own ~/apps/<name>/ alongside this one.
APP_DIR="$HOME/apps/scramble-challenge"
CHECKOUT_DIR="$HOME/apps/scramble-challenge/repo"
LAUNCHER_PATH="$HOME/apps/scramble-challenge/deploy-launcher.sh"

# Guard against running this on the wrong machine (e.g. a local PC instead of over SSH):
# it installs Docker.
if [ "$(uname -m)" != "aarch64" ]; then
  echo "This is $(hostname) ($(uname -m)), not the ARM server. SSH in first:" >&2
  echo "  ssh -i ~/.ssh/oci.key ubuntu@<server-ip>" >&2
  exit 1
fi

echo "== Installing Docker =="
sudo apt-get update
sudo apt-get install -y docker.io docker-compose-v2
sudo systemctl enable --now docker
sudo usermod -aG docker "$USER"

echo "== Creating the shared network the standalone Caddy stack reaches this app through =="
# docker-compose.yml declares this as external, so it must exist before the first
# `docker compose up`. Idempotent: safe to re-run server-setup.sh. Ports 80/443 and the
# Caddy stack itself are edge/server-setup.sh's concern, not this app's.
sudo docker network inspect scramble-challenge-edge > /dev/null 2>&1 \
  || sudo docker network create scramble-challenge-edge

echo "== Cloning the repo the launcher will keep up to date =="
mkdir -p "$APP_DIR"
if [ ! -d "$CHECKOUT_DIR/.git" ]; then
  git clone --depth 1 "$REPO_URL" "$CHECKOUT_DIR"
fi
chmod +x "$CHECKOUT_DIR/scripts/deploy.sh"

echo "== Installing the deploy launcher outside the checkout =="
# A sibling of $CHECKOUT_DIR (both under $APP_DIR), never inside it: it's the forced
# command below, and its job is to git-reset that checkout, which would rewrite itself
# out from under a running process if it lived there too. See scripts/deploy-launcher.sh
# for the full story.
cp "$CHECKOUT_DIR/scripts/deploy-launcher.sh" "$LAUNCHER_PATH"
chmod +x "$LAUNCHER_PATH"

echo "== Logging in to GHCR, if the images are private =="
echo "Leave this blank if you've made the ghcr.io packages public (recommended once"
echo "the repo itself is public) — deploys need no credentials then."
read -rsp "GHCR read-only token (Settings > Developer settings > read:packages), or blank: " GHCR_TOKEN
echo
if [ -n "$GHCR_TOKEN" ]; then
  echo "$GHCR_TOKEN" | docker login ghcr.io -u tdshaw2000 --password-stdin
fi
unset GHCR_TOKEN

echo "== Restricting the deploy key to the launcher =="
mkdir -p "$HOME/.ssh"
touch "$HOME/.ssh/authorized_keys"
RESTRICTION="command=\"$LAUNCHER_PATH\",no-agent-forwarding,no-X11-forwarding,no-port-forwarding,no-pty"
if ! grep -qF "$DEPLOY_KEY" "$HOME/.ssh/authorized_keys"; then
  echo "$RESTRICTION $DEPLOY_KEY" >> "$HOME/.ssh/authorized_keys"
fi
chmod 600 "$HOME/.ssh/authorized_keys"

echo
echo "Done. In the repo's GitHub settings, add these secrets, then push to main:"
echo "  DEPLOY_HOST       this server's IP or hostname"
echo "  DEPLOY_SSH_KEY    the deploy key's PRIVATE half"
