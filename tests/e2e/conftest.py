import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def live_server(tmp_path_factory):
    """The app running for real in a separate process, so browsers can use it."""
    port = free_port()
    database = tmp_path_factory.mktemp("e2e") / "e2e.db"
    process = subprocess.Popen(
        [sys.executable, "-m", "tests.e2e.server", "--port", str(port), "--database", str(database)],
        cwd=ROOT,
        env={**os.environ, "NO_PROXY": "127.0.0.1,localhost", "no_proxy": "127.0.0.1,localhost"},
    )
    url = f"http://127.0.0.1:{port}"
    for _ in range(100):
        try:
            urllib.request.urlopen(f"{url}/healthz")
            break
        except OSError:
            time.sleep(0.1)
    else:
        process.kill()
        raise RuntimeError("e2e server did not start")
    yield url
    process.terminate()
    process.wait()


@pytest.fixture(scope="session")
def browser_type_launch_args(browser_type_launch_args):
    # Lets a machine with a preinstalled Chromium point at it instead of
    # `playwright install chromium` (CI uses the install).
    executable = os.environ.get("PLAYWRIGHT_CHROMIUM_EXECUTABLE")
    return {**browser_type_launch_args, **({"executable_path": executable} if executable else {})}


@pytest.fixture
def new_player(browser, live_server):
    """A fresh phone-sized browser (its own cookies) for one player."""
    contexts = []

    def open_page():
        context = browser.new_context(viewport={"width": 390, "height": 844}, base_url=live_server)
        contexts.append(context)
        return context.new_page()

    yield open_page
    for context in contexts:
        context.close()


def control(live_server, action, **params):
    query = "&".join(f"{k}={v}" for k, v in params.items())
    request = urllib.request.Request(f"{live_server}/__test__/{action}?{query}", method="POST")
    urllib.request.urlopen(request)
