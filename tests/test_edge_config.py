"""The standalone Caddy stack (edge/) that fronts scramble-challenge and any other app
sharing its "scramble-challenge-edge" Docker network. Its own Compose project, so that
redeploying scramble-challenge's own stack never restarts it, and vice versa. Deployment
files can't be unit tested for real -- CI's smoke test is the proof; these tests pin down
what the files must do."""

import os
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1] / "edge"
EDGE_NETWORK = "scramble-challenge-edge"


@pytest.fixture(scope="module")
def compose():
    return yaml.safe_load((ROOT / "compose.yaml").read_text())


def text(path):
    return (ROOT / path).read_text()


def test_caddy_serves_http_and_https_and_keeps_its_certificates(compose):
    caddy = compose["services"]["caddy"]

    assert caddy["image"].startswith("caddy:2")
    assert {"80:80", "443:443"} <= set(caddy["ports"])
    assert "./Caddyfile:/etc/caddy/Caddyfile:ro" in caddy["volumes"]
    assert "caddy_data:/data" in caddy["volumes"]
    assert "caddy_data" in compose["volumes"]


def test_caddy_is_its_own_compose_project(compose):
    # So that neither scramble-challenge's nor wca-records-analyser's own deploy ever
    # restarts this stack as a side effect of restarting theirs.
    assert compose["name"] == "caddy"


def test_caddy_site_defaults_to_plain_http_so_ci_needs_no_domain(compose):
    caddy_env = compose["services"]["caddy"]["environment"]
    assert caddy_env["SCRCH_SITE_ADDRESS"] == "${SCRCH_SITE_ADDRESS:-:80}"


def test_caddy_proxies_the_site_address_to_scramble_challenges_web():
    caddyfile = text("Caddyfile")

    assert "{$SCRCH_SITE_ADDRESS}" in caddyfile
    assert "reverse_proxy scramble-web:5000" in caddyfile


def test_wca_records_analyser_site_defaults_to_plain_http_so_ci_needs_no_domain(compose):
    # Same trick as SCRCH_SITE_ADDRESS: a bare port, not a real domain, so CI and local
    # `docker compose up` never trigger a live Let's Encrypt ACME challenge for a
    # production hostname the runner doesn't own.
    caddy_env = compose["services"]["caddy"]["environment"]
    assert caddy_env["WCA_SITE_ADDRESS"] == "${WCA_SITE_ADDRESS:-:8080}"


def test_caddy_proxies_wca_site_address_to_the_other_app():
    caddyfile = text("Caddyfile")

    assert "{$WCA_SITE_ADDRESS}" in caddyfile
    assert "reverse_proxy wca-records-analyser:8000" in caddyfile


def test_caddy_joins_the_shared_external_network_so_it_can_reach_either_app(compose):
    caddy = compose["services"]["caddy"]

    assert caddy["networks"] == ["edge"]
    edge = compose["networks"]["edge"]
    assert edge["external"] is True
    assert edge["name"] == EDGE_NETWORK


def test_server_setup_script_is_valid_and_executable():
    script = ROOT / "server-setup.sh"

    assert os.access(script, os.X_OK)
    subprocess.run(["bash", "-n", str(script)], check=True)


def test_server_setup_opens_web_ports_before_docker_touches_the_firewall():
    script = text("server-setup.sh")

    opens_ports = script.index("--dports 80,443")
    saves_rules = script.index("netfilter-persistent save")
    assert opens_ports < saves_rules


def test_server_setup_refuses_to_run_anywhere_but_an_arm_server():
    script = text("server-setup.sh")

    checks_arch = script.index('"$(uname -m)" != "aarch64"')
    first_change = script.index("sudo ")
    assert checks_arch < first_change


def test_server_setup_creates_the_shared_edge_network_once():
    script = text("server-setup.sh")

    assert f"docker network create {EDGE_NETWORK}" in script
    # Idempotent: re-running server-setup.sh (or a second server) must not fail because
    # the network already exists.
    creates = script.index(f"docker network create {EDGE_NETWORK}")
    guard = script.rfind("docker network inspect", 0, creates)
    assert guard != -1, "network create isn't guarded by an existence check"


def test_server_setup_installs_this_stacks_files_under_its_own_apps_dir():
    # Mirrors scramble-challenge's own ~/apps/<name>/ convention (server-layout-cleanup).
    script = text("server-setup.sh")

    assert "$HOME/apps/caddy" in script
    assert "compose.yaml" in script
    assert "Caddyfile" in script
