"""How the admin password reaches the live server: a script writes it to a file outside
the repo checkout, and docker compose hands that file to the web container."""

import importlib.util
import stat
from pathlib import Path

import pytest
import yaml
from werkzeug.security import check_password_hash

ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = "/etc/scramble-challenge/admin.env"


@pytest.fixture(scope="module")
def script():
    spec = importlib.util.spec_from_file_location(
        "set_admin_password", ROOT / "scripts/set_admin_password.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_env(path: Path) -> dict[str, str]:
    pairs = (line.split("=", 1) for line in path.read_text().splitlines() if line)
    return {key: value for key, value in pairs}


def test_compose_gives_the_web_container_the_admin_file_if_it_exists():
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text())

    assert compose["services"]["web"]["env_file"] == [{"path": ENV_FILE, "required": False}]


def test_script_writes_to_the_file_compose_reads_by_default(script):
    assert script.ENV_FILE == ENV_FILE


def test_script_writes_a_hash_the_app_accepts_and_a_random_secret_key(script, tmp_path):
    env_file = tmp_path / "admin.env"

    script.write_env_file(env_file, "correct horse")
    first = read_env(env_file)
    script.write_env_file(env_file, "correct horse")
    second = read_env(env_file)

    # Single quotes stop compose treating the hash's "$" signs as variables.
    assert first["ADMIN_PASSWORD_HASH"].startswith("'scrypt:")
    assert first["ADMIN_PASSWORD_HASH"].endswith("'")
    assert check_password_hash(first["ADMIN_PASSWORD_HASH"].strip("'"), "correct horse")
    assert not check_password_hash(first["ADMIN_PASSWORD_HASH"].strip("'"), "wrong")
    assert len(first["SECRET_KEY"].strip("'")) >= 32
    assert first["SECRET_KEY"] != second["SECRET_KEY"]
    assert first["ADMIN_PASSWORD_HASH"] != second["ADMIN_PASSWORD_HASH"]  # fresh salt


def test_script_makes_the_file_readable_only_by_its_owner(script, tmp_path):
    env_file = tmp_path / "sub" / "admin.env"

    script.write_env_file(env_file, "correct horse")

    assert stat.S_IMODE(env_file.stat().st_mode) == 0o600


def test_script_accepts_a_password_of_any_length(script, tmp_path):
    env_file = tmp_path / "admin.env"

    script.write_env_file(env_file, "x")

    assert check_password_hash(read_env(env_file)["ADMIN_PASSWORD_HASH"].strip("'"), "x")


def test_script_refuses_an_empty_password(script, tmp_path):
    with pytest.raises(ValueError, match="can't be empty"):
        script.write_env_file(tmp_path / "admin.env", "")


def test_script_hands_the_file_to_the_given_owner_so_the_deploy_can_read_it(
    script, tmp_path, monkeypatch
):
    # Compose reads env_file as the user running it (the runner's "ubuntu" account),
    # so a root-only file would break every deploy. Changing a file's owner needs root,
    # which tests don't have, so record the call instead.
    chowned = []
    monkeypatch.setattr(script.os, "chown", lambda *args: chowned.append(args))
    env_file = tmp_path / "admin.env"

    script.write_env_file(env_file, "correct horse", owner=(1234, 5678))

    assert chowned == [(env_file, 1234, 5678)]


@pytest.mark.parametrize(
    ("environ", "owner"),
    [
        ({"SUDO_UID": "1000", "SUDO_GID": "1001"}, (1000, 1001)),
        ({}, None),  # not run with sudo: the file stays with whoever ran it
    ],
)
def test_script_gives_the_file_to_whoever_ran_sudo(script, environ, owner):
    assert script.sudo_owner(environ) == owner
