"""The production server (gunicorn.conf.py + app.wsgi, as docker/web/entrypoint.sh runs
it) must keep serving pages while many players hold WebSockets open. Each open game tab
holds one WebSocket for the whole game."""

import os
import signal
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PLAYERS = 20

UPGRADE = (
    b"GET /socket.io/?EIO=4&transport=websocket HTTP/1.1\r\n"
    b"Host: localhost\r\n"
    b"Upgrade: websocket\r\n"
    b"Connection: Upgrade\r\n"
    b"Sec-WebSocket-Key: c21va2UtdGVzdC1rZXkhIQ==\r\n"
    b"Sec-WebSocket-Version: 13\r\n\r\n"
)


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def healthz(port, timeout):
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/healthz", timeout=timeout) as r:
        return r.status


@pytest.fixture
def production_server(tmp_path):
    port = free_port()
    env = {
        **os.environ,
        "DATABASE_URL": f"sqlite:///{tmp_path / 'scramble.db'}",
        "TNOODLE_URL": "http://tnoodle.invalid",
        "FLASK_APP": "app:create_app",
        "NO_PROXY": "127.0.0.1,localhost",
        "no_proxy": "127.0.0.1,localhost",
    }
    subprocess.run(
        [sys.executable, "-m", "flask", "db", "upgrade"],
        cwd=ROOT,
        env=env,
        check=True,
        capture_output=True,
    )
    server = subprocess.Popen(
        [sys.executable, "-m", "gunicorn", "-c", "gunicorn.conf.py"]
        + ["--bind", f"127.0.0.1:{port}", "app.wsgi:app"],
        cwd=ROOT,
        env=env,
        start_new_session=True,  # so teardown can stop gunicorn and its worker together
    )
    for _ in range(100):
        try:
            healthz(port, timeout=1)
            break
        except OSError:
            time.sleep(0.1)
    yield port
    # A stuck worker never finishes a graceful shutdown, so don't wait for one.
    os.killpg(server.pid, signal.SIGKILL)
    server.wait(timeout=10)


def open_websocket(port):
    """A game tab's connection: the WebSocket upgrade, then left open."""
    connection = socket.create_connection(("127.0.0.1", port), timeout=5)
    connection.sendall(UPGRADE)
    assert connection.recv(1024).startswith(b"HTTP/1.1 101")
    return connection


def test_pages_still_load_while_twenty_players_hold_websockets_open(production_server):
    connections = []
    try:
        for _ in range(PLAYERS):
            connections.append(open_websocket(production_server))

        assert healthz(production_server, timeout=5) == 200
    finally:
        for connection in connections:
            connection.close()
