"""Deployment files can't be unit tested for real: CI's smoke test and the first deploy
are the proof. These tests pin down what the files must do."""

import os
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
SITE = "scramble-challenge.duckdns.org"


@pytest.fixture(scope="module")
def compose():
    return yaml.safe_load((ROOT / "docker-compose.yml").read_text())


@pytest.fixture(scope="module")
def deploy():
    workflow = yaml.safe_load((ROOT / ".github/workflows/ci.yml").read_text())
    return workflow["jobs"]["deploy"]


def text(path):
    return (ROOT / path).read_text()


def test_caddy_serves_http_and_https_and_keeps_its_certificates(compose):
    caddy = compose["services"]["caddy"]

    assert caddy["image"].startswith("caddy:2")
    assert {"80:80", "443:443"} <= set(caddy["ports"])
    assert "./docker/caddy/Caddyfile:/etc/caddy/Caddyfile:ro" in caddy["volumes"]
    assert "caddy_data:/data" in caddy["volumes"]
    assert "caddy_data" in compose["volumes"]


def test_caddy_site_defaults_to_plain_http_so_ci_needs_no_domain(compose):
    assert compose["services"]["caddy"]["environment"]["SITE_ADDRESS"] == "${SITE_ADDRESS:-:80}"


def test_caddy_proxies_the_site_address_to_the_web_app():
    caddyfile = text("docker/caddy/Caddyfile")

    assert "{$SITE_ADDRESS}" in caddyfile
    assert "reverse_proxy web:5000" in caddyfile


def test_web_is_reachable_only_through_caddy_and_trusts_it(compose):
    web = compose["services"]["web"]

    assert web["ports"] == ["127.0.0.1:${WEB_PORT:-5000}:5000"]
    assert web["environment"]["TRUSTED_PROXIES"] == "1"


def test_smoke_test_checks_pages_and_websockets_through_caddy():
    script = text("scripts/smoke-test.sh")

    assert "SITE_ADDRESS" in script
    assert "Upgrade: websocket" in script
    assert "101" in script


def test_deploy_runs_on_the_servers_runner_after_publishing(deploy):
    assert deploy["runs-on"] == ["self-hosted", "oci"]
    assert deploy["needs"] == ["publish"]
    assert deploy["if"] == "github.event_name == 'push' && github.ref == 'refs/heads/main'"
    assert deploy["permissions"]["packages"] == "read"


def test_deploy_pulls_restarts_and_smoke_tests_the_live_site(deploy):
    run = "\n".join(step.get("run", "") for step in deploy["steps"])

    assert deploy["env"]["SITE_ADDRESS"] == SITE
    assert "docker compose pull" in run
    assert "docker compose up -d" in run
    assert "scripts/smoke-test.sh" in run


def test_server_setup_script_is_valid_and_executable():
    script = ROOT / "scripts/server-setup.sh"

    assert os.access(script, os.X_OK)
    subprocess.run(["bash", "-n", str(script)], check=True)


def test_server_setup_opens_web_ports_before_docker_touches_the_firewall():
    script = text("scripts/server-setup.sh")

    opens_ports = script.index("--dports 80,443")
    saves_rules = script.index("netfilter-persistent save")
    installs_docker = script.index("docker.io")
    assert opens_ports < saves_rules < installs_docker


def test_server_setup_registers_an_arm_runner_labelled_oci_as_a_service():
    script = text("scripts/server-setup.sh")

    assert "linux-arm64" in script
    assert "--labels oci" in script
    assert "svc.sh install" in script


def test_server_setup_refuses_to_run_anywhere_but_an_arm_server():
    script = text("scripts/server-setup.sh")

    checks_arch = script.index('"$(uname -m)" != "aarch64"')
    first_change = script.index("sudo ")
    assert checks_arch < first_change


def test_production_dependencies_include_what_gunicorns_gevent_worker_imports():
    # The image installs without dev dependencies, and gunicorn's gevent worker imports
    # "packaging", which gunicorn itself doesn't declare. Locally dev tools bring it in.
    exported = subprocess.run(
        ["uv", "export", "--frozen", "--no-dev", "--no-hashes"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    packages = {line.split("==")[0] for line in exported.splitlines() if "==" in line}
    assert {"gunicorn", "gevent", "packaging"} <= packages
