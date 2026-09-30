"""Deployment files can't be unit tested for real: CI's smoke test and the first deploy
are the proof. These tests pin down what the files must do."""

import os
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
SITE = "scramble-challenge.duckdns.org"
WCA_SITE = "wca-records-analyser.duckdns.org"
EDGE_NETWORK = "scramble-challenge-edge"


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


def test_wca_records_analyser_site_defaults_to_plain_http_so_ci_needs_no_domain(compose):
    # Same trick as SITE_ADDRESS: a bare port, not a real domain, so CI and local
    # `docker compose up` never trigger a live Let's Encrypt ACME challenge for a
    # production hostname the runner doesn't own.
    caddy_env = compose["services"]["caddy"]["environment"]
    assert caddy_env["WCA_SITE_ADDRESS"] == "${WCA_SITE_ADDRESS:-:8080}"


def test_caddy_proxies_wca_site_address_to_the_other_app():
    caddyfile = text("docker/caddy/Caddyfile")

    assert "{$WCA_SITE_ADDRESS}" in caddyfile
    assert "reverse_proxy wca-records-analyser:8000" in caddyfile


def test_caddy_joins_a_shared_external_network_so_it_can_reach_other_apps(compose):
    # wca-records-analyser is a separate app with its own compose project, so Caddy can
    # only resolve its container name if both stacks join a network created outside of
    # (and shared between) either project.
    caddy = compose["services"]["caddy"]

    assert set(caddy["networks"]) == {"default", "edge"}
    edge = compose["networks"]["edge"]
    assert edge["external"] is True
    assert edge["name"] == EDGE_NETWORK


def test_only_caddy_joins_the_shared_edge_network(compose):
    # The other services have no business being reachable from outside this stack.
    for name, service in compose["services"].items():
        if name != "caddy":
            assert "networks" not in service


def test_web_is_reachable_only_through_caddy_and_trusts_it(compose):
    web = compose["services"]["web"]

    assert web["ports"] == ["127.0.0.1:${WEB_PORT:-5000}:5000"]
    assert web["environment"]["TRUSTED_PROXIES"] == "1"


def test_smoke_test_checks_pages_and_websockets_through_caddy():
    script = text("scripts/smoke-test.sh")

    assert "SITE_ADDRESS" in script
    assert "Upgrade: websocket" in script
    assert "101" in script


def test_deploy_runs_on_a_github_hosted_runner_over_ssh_after_publishing(deploy):
    # No self-hosted runner: a public repo's pull requests would otherwise be able to
    # target it and run arbitrary code on the server. A hosted runner only ever holds
    # the SSH key needed to trigger scripts/deploy.sh remotely.
    assert deploy["runs-on"] == "ubuntu-latest"
    assert deploy["needs"] == ["publish"]
    assert deploy["if"] == "github.event_name == 'push' && github.ref == 'refs/heads/main'"


def test_deploy_never_checks_out_the_repository(deploy):
    # A checkout isn't needed (the server has its own clone) and, more importantly,
    # avoids ever handing this job's GITHUB_TOKEN to anything that could act on it.
    assert "actions/checkout@v4" not in [step.get("uses", "") for step in deploy["steps"]]


def test_deploy_uses_an_ssh_key_scoped_to_this_job_only(deploy):
    steps = deploy["steps"]
    agent = next(s for s in steps if s.get("uses", "").startswith("webfactory/ssh-agent"))
    assert agent["with"]["ssh-private-key"] == "${{ secrets.DEPLOY_SSH_KEY }}"


def test_deploy_pins_the_servers_host_key_before_connecting(deploy):
    run = "\n".join(step.get("run", "") for step in deploy["steps"])
    assert "ssh-keyscan" in run
    assert "${{ secrets.DEPLOY_HOST }}" in run


def test_deploy_runs_nothing_but_the_forced_remote_command(deploy):
    # The SSH key is restricted server-side (see server-setup.sh) to always run
    # scripts/deploy.sh, whatever command the client sends, so the workflow itself
    # never names a remote command to run.
    run = "\n".join(step.get("run", "") for step in deploy["steps"])
    ssh_lines = [line for line in run.splitlines() if line.strip().startswith("ssh ")]
    assert ssh_lines
    for line in ssh_lines:
        assert "${{ secrets.DEPLOY_HOST }}" in line


def test_smoke_creates_the_shared_edge_network_before_compose_up():
    # docker-compose.yml declares "edge" as external, so smoke's own `docker compose up`
    # needs it to already exist.
    workflow = yaml.safe_load((ROOT / ".github/workflows/ci.yml").read_text())
    runs = [step.get("run", "") for step in workflow["jobs"]["smoke"]["steps"]]

    network = next(i for i, run in enumerate(runs) if EDGE_NETWORK in run)
    up = next(i for i, run in enumerate(runs) if run.startswith("docker compose up -d"))
    assert network < up


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


def test_server_setup_has_no_self_hosted_runner_left():
    script = text("scripts/server-setup.sh")

    assert "actions-runner" not in script
    assert "svc.sh" not in script


def test_server_setup_clones_the_repo_once_for_deploys():
    script = text("scripts/server-setup.sh")

    assert "git clone" in script
    clones = script.index("git clone")
    # Idempotent: re-running server-setup.sh must not fail on an existing checkout.
    guard = script.rfind("[ ! -d", 0, clones)
    assert guard != -1, "git clone isn't guarded by an existence check"


def test_server_setup_restricts_the_deploy_key_to_deploy_sh():
    script = text("scripts/server-setup.sh")

    assert 'command="' in script
    assert "scripts/deploy.sh" in script
    for restriction in ("no-agent-forwarding", "no-X11-forwarding", "no-port-forwarding", "no-pty"):
        assert restriction in script


def test_server_setup_appending_the_deploy_key_is_idempotent():
    script = text("scripts/server-setup.sh")

    assert "authorized_keys" in script
    appends = script.index(">> \"$HOME/.ssh/authorized_keys\"")
    guard = script.rfind("grep", 0, appends)
    assert guard != -1, "the key is appended without checking it isn't there already"


def test_server_setup_creates_the_shared_edge_network_once():
    script = text("scripts/server-setup.sh")

    assert f"docker network create {EDGE_NETWORK}" in script
    # Idempotent: re-running server-setup.sh (or a second server) must not fail because
    # the network already exists.
    creates = script.index(f"docker network create {EDGE_NETWORK}")
    guard = script.rfind("docker network inspect", 0, creates)
    assert guard != -1, "network create isn't guarded by an existence check"


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


BACKUP = "docker compose run --rm --no-deps backup python -m app.backup"


def test_a_backup_service_takes_nightly_snapshots_onto_its_own_volume(compose):
    backup = compose["services"]["backup"]
    web = compose["services"]["web"]

    assert backup["image"] == web["image"]
    assert backup["command"] == ["python", "-m", "app.backup", "schedule"]
    assert backup["restart"] == "unless-stopped"
    # An init process passes on the stop signal, so deploys don't wait 10s to kill it.
    assert backup["init"] is True
    assert backup["environment"]["DATABASE_URL"] == web["environment"]["DATABASE_URL"]
    assert backup["environment"]["BACKUP_DIR"] == "/backups"
    assert {"data:/data", "backups:/backups"} <= set(backup["volumes"])
    assert "backups" in compose["volumes"]
    # The web app never needs to see the snapshots.
    assert "backups:/backups" not in web["volumes"]


def test_deploy_script_is_valid_and_executable():
    script = ROOT / "scripts/deploy.sh"

    assert os.access(script, os.X_OK)
    subprocess.run(["bash", "-n", str(script)], check=True)


def test_deploy_script_updates_the_checkout_before_using_it():
    script = text("scripts/deploy.sh")

    assert "git fetch" in script
    fetch = script.index("git fetch")
    pull = script.index("docker compose pull")
    assert fetch < pull


def test_deploy_script_snapshots_the_database_with_the_new_image_before_restarting():
    script = text("scripts/deploy.sh")

    pull = script.index("docker compose pull")
    snapshot = script.index(f"{BACKUP} snapshot predeploy")
    up = script.index("docker compose up -d")
    assert pull < snapshot < up


def test_deploy_script_creates_the_shared_edge_network_before_compose_up():
    script = text("scripts/deploy.sh")

    network = script.index(EDGE_NETWORK)
    up = script.index("docker compose up -d")
    assert network < up


def test_deploy_script_sets_both_real_domains_and_smoke_tests_the_live_site():
    script = text("scripts/deploy.sh")

    assert SITE in script
    assert WCA_SITE in script
    assert "scripts/smoke-test.sh" in script
