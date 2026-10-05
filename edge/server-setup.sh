#!/bin/bash
# One-time setup for the standalone Caddy stack that fronts scramble-challenge (and any
# other app sharing its "scramble-challenge-edge" Docker network). Run it on the server:
#
#   bash server-setup.sh
#
# Updating the Caddyfile or compose.yaml later is manual -- see README.md "Deploying a
# change" -- this only needs to run once per server.
set -euo pipefail

cd "$(dirname "$0")"

# Everything for this stack lives under its own folder, mirroring the ~/apps/<name>/
# convention scramble-challenge's own server-setup.sh uses.
APP_DIR="$HOME/apps/caddy"

# Guard against running this on the wrong machine (e.g. a local PC instead of over SSH):
# it changes the firewall.
if [ "$(uname -m)" != "aarch64" ]; then
  echo "This is $(hostname) ($(uname -m)), not the ARM server. SSH in first:" >&2
  echo "  ssh -i ~/.ssh/oci.key ubuntu@<server-ip>" >&2
  exit 1
fi

echo "== Opening ports 80 and 443 in the server's own firewall =="
# OCI's Ubuntu images reject incoming traffic in iptables even when the cloud security
# list allows it. Save these rules before Docker starts adding its own.
if ! sudo iptables -C INPUT -p tcp -m multiport --dports 80,443 -m conntrack --ctstate NEW -j ACCEPT 2> /dev/null; then
  sudo iptables -I INPUT -p tcp -m multiport --dports 80,443 -m conntrack --ctstate NEW -j ACCEPT
fi
sudo apt-get update
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y iptables-persistent
sudo netfilter-persistent save

echo "== Creating the shared network apps reach this Caddy through =="
# Each app's own compose.yaml declares this as external, so it must exist before any
# of them (including this one) run `docker compose up`. Idempotent: safe to re-run.
docker network inspect scramble-challenge-edge > /dev/null 2>&1 \
  || docker network create scramble-challenge-edge

echo "== Installing this stack's files =="
mkdir -p "$APP_DIR"
cp compose.yaml Caddyfile "$APP_DIR/"

echo
echo "Done. Add $APP_DIR/.env with the real SITE_ADDRESS and WCA_SITE_ADDRESS domains,"
echo "then: cd $APP_DIR && docker compose up -d"
