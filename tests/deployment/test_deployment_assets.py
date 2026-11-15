from __future__ import annotations

import os
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).parents[2]


def test_at037_dockerfile_is_locked_labeled_and_non_root() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "FROM python:3.13.9-slim-bookworm" in dockerfile
    assert "ghcr.io/astral-sh/uv:0.13.8" in dockerfile
    assert dockerfile.count("uv sync --frozen --no-dev") == 2
    assert 'org.opencontainers.image.revision="${GIT_SHA}"' in dockerfile
    assert 'org.opencontainers.image.version="${RELEASE_VERSION}"' in dockerfile
    assert "USER 10001:10001" in dockerfile
    assert "stock_agent.api.app:app" in dockerfile
    assert "LIVE_TRADING_ENABLED=false" in dockerfile
    assert "COPY . ." not in dockerfile


def test_at038_render_blueprint_is_development_paper_only_and_secret_safe() -> None:
    blueprint = yaml.safe_load((ROOT / "render.yaml").read_text(encoding="utf-8"))
    assert set(blueprint) == {"services", "databases"}
    service = blueprint["services"][0]
    assert service["type"] == "web"
    assert service["runtime"] == "docker"
    assert service["numInstances"] == 1
    assert service["healthCheckPath"] == "/health/ready"
    assert service["preDeployCommand"] == "./scripts/deployment/predeploy.sh"
    assert service["autoDeployTrigger"] == "checksPass"
    env = {item["key"]: item for item in service["envVars"]}
    assert env["ENVIRONMENT"]["value"] == "development"
    assert env["BROKER_MODE"]["value"] == "FAKE"
    assert env["LIVE_TRADING_ENABLED"]["value"] == "false"
    assert env["DATABASE_URL"]["fromDatabase"]["property"] == "connectionString"
    for secret in (
        "DEV_TEST_TOKEN",
        "MODEL_API_KEY",
        "ALPACA_PAPER_KEY",
        "ALPACA_PAPER_SECRET",
    ):
        assert env[secret] == {"key": secret, "sync": False}
    rendered = (ROOT / "render.yaml").read_text(encoding="utf-8").lower()
    assert "api.alpaca.markets" not in rendered
    assert "password:" not in rendered


def test_at039_predeploy_fails_closed_before_migration() -> None:
    script = ROOT / "scripts/deployment/predeploy.sh"
    unsafe = subprocess.run(  # noqa: S603 -- executes a repository-owned test fixture.
        ["/bin/bash", str(script)],
        cwd=ROOT,
        env={**os.environ, "LIVE_TRADING_ENABLED": "true", "BROKER_MODE": "FAKE"},
        text=True,
        capture_output=True,
        check=False,
    )
    assert unsafe.returncode == 1
    assert "LIVE_TRADING_ENABLED must be false" in unsafe.stderr

    missing_database = subprocess.run(  # noqa: S603 -- repository-owned test fixture.
        ["/bin/bash", str(script)],
        cwd=ROOT,
        env={
            **os.environ,
            "LIVE_TRADING_ENABLED": "false",
            "BROKER_MODE": "FAKE",
            "DATABASE_URL": "",
        },
        text=True,
        capture_output=True,
        check=False,
    )
    assert missing_database.returncode == 1
    assert "DATABASE_URL is required" in missing_database.stderr


def test_deployment_scripts_are_syntax_valid_and_rollback_defaults_to_dry_run() -> None:
    scripts = sorted((ROOT / "scripts/deployment").glob("*.sh"))
    assert scripts
    for script in scripts:
        subprocess.run(  # noqa: S603 -- validates repository-owned scripts.
            ["/bin/bash", "-n", str(script)], check=True
        )

    rollback = subprocess.run(  # noqa: S603 -- executes a repository-owned dry-run fixture.
        [
            "/bin/bash",
            str(ROOT / "scripts/deployment/rollback.sh"),
            "srv-dev",
            "dep-known-good",
        ],
        cwd=ROOT,
        env={**os.environ, "RENDER_API_KEY": "test-placeholder"},
        text=True,
        capture_output=True,
        check=False,
    )
    assert rollback.returncode == 3
    assert "DRY RUN" in rollback.stderr
    assert "alembic downgrade" not in (ROOT / "scripts/deployment/rollback.sh").read_text()


def test_docker_context_excludes_secrets_and_test_artifacts() -> None:
    ignored = set((ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines())
    assert {".git", ".venv", ".env", ".env.*", "tests", ".codex"}.issubset(ignored)
