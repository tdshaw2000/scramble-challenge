#!/usr/bin/env python3
"""Set the admin area's password on the server.

Run on the server:  sudo python3 scripts/set_admin_password.py
Then re-run the latest deploy on GitHub so the web container picks it up.

Uses only the standard library, so it runs on the server without installing anything.
The hash is in werkzeug's scrypt format, which the app checks with check_password_hash.
"""

import getpass
import hashlib
import os
import secrets
import sys
from pathlib import Path

ENV_FILE = "/etc/scramble-challenge/admin.env"
MIN_LENGTH = 12
N, R, P = 32768, 8, 1  # werkzeug's scrypt defaults


def password_hash(password: str) -> str:
    salt = secrets.token_urlsafe(12)[:16]
    digest = hashlib.scrypt(
        password.encode(), salt=salt.encode(), n=N, r=R, p=P, maxmem=132 * N * R * P, dklen=64
    )
    return f"scrypt:{N}:{R}:{P}${salt}${digest.hex()}"


def sudo_owner(environ) -> tuple[int, int] | None:
    """The account that ran sudo. It must own the file: docker compose reads env_file
    as the user running it, which on the server is the runner's account, not root."""
    if "SUDO_UID" in environ:
        return int(environ["SUDO_UID"]), int(environ["SUDO_GID"])
    return None


def write_env_file(path, password: str, owner: tuple[int, int] | None = None) -> None:
    if len(password) < MIN_LENGTH:
        raise ValueError(f"The password must be at least {MIN_LENGTH} characters.")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Single quotes stop docker compose treating the "$" signs in the hash as variables.
    content = (
        f"ADMIN_PASSWORD_HASH='{password_hash(password)}'\n"
        f"SECRET_KEY='{secrets.token_urlsafe(32)}'\n"
    )
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as file:
        file.write(content)
    os.chmod(path, 0o600)  # in case the file already existed with looser permissions
    if owner:
        os.chown(path, *owner)


def main() -> int:
    password = getpass.getpass("New admin password: ")
    if getpass.getpass("Type it again: ") != password:
        print("The passwords didn't match; nothing changed.")
        return 1
    try:
        write_env_file(ENV_FILE, password, owner=sudo_owner(os.environ))
    except ValueError as error:
        print(f"{error} Nothing changed.")
        return 1
    except PermissionError:
        print(f"Can't write {ENV_FILE}; run this with sudo.")
        return 1
    print(f"Saved to {ENV_FILE}. Now re-run the latest deploy on GitHub (Actions tab).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
