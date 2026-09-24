"""The GitHub Actions workflow can't run here, so these tests pin down what it must do.
The real proof is CI going green on a pull request."""

from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def workflow():
    return yaml.safe_load((ROOT / ".github/workflows/ci.yml").read_text())


@pytest.fixture(scope="module")
def compose():
    return yaml.safe_load((ROOT / "docker-compose.yml").read_text())


def triggers(workflow):
    # YAML 1.1 reads the bare key `on` as the boolean True.
    return workflow.get("on", workflow.get(True))


def commands(job):
    return "\n".join(step.get("run", "") for step in job["steps"])


def uses(job):
    return [step.get("uses", "") for step in job["steps"]]


def test_ci_runs_on_every_pull_request_and_on_pushes_to_main(workflow):
    on = triggers(workflow)

    assert "pull_request" in on
    assert on["push"]["branches"] == ["main"]


def test_ci_lints_and_runs_every_test_including_the_browser_tests(workflow):
    run = commands(workflow["jobs"]["test"])

    assert "uv sync --frozen" in run
    assert "ruff check" in run and "ruff format --check" in run
    assert "playwright install --with-deps chromium" in run
    assert "uv run pytest\n" in run + "\n"


def test_ci_checks_the_fake_tnoodle_against_the_real_one(workflow):
    run = commands(workflow["jobs"]["tnoodle-contract"])

    assert "docker/tnoodle" in run
    assert "uv run pytest -m tnoodle" in run


def test_ci_smoke_tests_the_docker_compose_stack(workflow):
    run = commands(workflow["jobs"]["smoke"])

    assert "docker compose up" in run
    assert "scripts/smoke-test.sh" in run


def test_images_are_published_only_from_main_after_every_check_passes(workflow):
    publish = workflow["jobs"]["publish"]

    assert publish["if"] == "github.event_name == 'push' && github.ref == 'refs/heads/main'"
    assert set(publish["needs"]) == {"test", "tnoodle-contract", "smoke"}
    assert publish["permissions"]["packages"] == "write"


def test_images_are_built_for_the_arm_server(workflow):
    publish = workflow["jobs"]["publish"]
    builds = [s for s in publish["steps"] if s.get("uses", "").startswith("docker/build-push")]

    assert any(u.startswith("docker/setup-qemu-action") for u in uses(publish))
    assert builds
    for step in builds:
        assert "linux/arm64" in step["with"]["platforms"]


def test_published_image_names_match_docker_compose(workflow, compose):
    publish = workflow["jobs"]["publish"]
    text = yaml.safe_dump(publish)

    for service in ("web", "tnoodle"):
        image = compose["services"][service]["image"]
        name = image.rsplit(":", 1)[0].replace(
            "tdshaw2000/scramble-challenge", "${{ github.repository }}"
        )
        assert name in text, f"publish job never pushes {name}"
