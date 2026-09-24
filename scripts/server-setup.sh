#!/bin/bash
# One-time setup for the OCI server (Ubuntu 24.04, ARM). Run it on the server as the
# default "ubuntu" user:
#
#   bash server-setup.sh <runner-registration-token>
#
# The token comes from GitHub: repo Settings > Actions > Runners > New self-hosted
# runner (it's single-use and expires after an hour). After this, every push to main
# deploys here automatically.
set -euo pipefail

TOKEN="${1:?Usage: bash server-setup.sh <runner-registration-token>}"
REPO_URL="https://github.com/tdshaw2000/scramble-challenge"
RUNNER_DIR="$HOME/actions-runner"

echo "== Opening ports 80 and 443 in the server's own firewall =="
# OCI's Ubuntu images reject incoming traffic in iptables even when the cloud security
# list allows it. Save these rules before Docker starts adding its own.
if ! sudo iptables -C INPUT -p tcp -m multiport --dports 80,443 -m conntrack --ctstate NEW -j ACCEPT 2> /dev/null; then
  sudo iptables -I INPUT -p tcp -m multiport --dports 80,443 -m conntrack --ctstate NEW -j ACCEPT
fi
sudo apt-get update
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y iptables-persistent
sudo netfilter-persistent save

echo "== Installing Docker =="
sudo apt-get install -y docker.io docker-compose-v2
sudo systemctl enable --now docker
sudo usermod -aG docker "$USER"

echo "== Installing the GitHub Actions runner =="
VERSION=$(curl -fsSL https://api.github.com/repos/actions/runner/releases/latest \
  | grep -o '"tag_name": *"v[^"]*"' | grep -o '[0-9][0-9.]*')
mkdir -p "$RUNNER_DIR"
cd "$RUNNER_DIR"
curl -fsSL -o runner.tar.gz \
  "https://github.com/actions/runner/releases/download/v${VERSION}/actions-runner-linux-arm64-${VERSION}.tar.gz"
tar xzf runner.tar.gz
rm runner.tar.gz

./config.sh --unattended --replace \
  --url "$REPO_URL" \
  --token "$TOKEN" \
  --name scramble-challenge-oci \
  --labels oci

# A system service keeps the runner going after you log out and across reboots.
sudo ./svc.sh install "$USER"
sudo ./svc.sh start

echo
echo "Done. The runner shows as Idle under Settings > Actions > Runners."
echo "Re-run the latest CI workflow on main (or push to main) to deploy."
