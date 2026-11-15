from __future__ import annotations

import secrets
from collections.abc import Callable

from fastapi import FastAPI, Header, HTTPException
from sqlalchemy import create_engine, text

from stock_agent import __version__
from stock_agent.release import load_release_manifest
from stock_agent.settings import Settings

ReadinessProbe = Callable[[], tuple[bool, str]]
EXPECTED_ALEMBIC_REVISION = "0001"


def database_readiness_probe(database_url: str) -> tuple[bool, str]:
    try:
        engine = create_engine(database_url, pool_pre_ping=True)
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
                revision = connection.execute(
                    text("SELECT version_num FROM alembic_version")
                ).scalar_one_or_none()
        finally:
            engine.dispose()
    except Exception:  # readiness must fail closed without leaking connection details
        return False, "database_unavailable"
    if revision != EXPECTED_ALEMBIC_REVISION:
        return False, "migration_not_current"
    return True, "ready"


def create_app(
    settings: Settings | None = None,
    readiness_probe: ReadinessProbe | None = None,
) -> FastAPI:
    configured = settings or Settings()
    probe = readiness_probe
    if probe is None and configured.require_database_readiness:
        def configured_database_probe() -> tuple[bool, str]:
            return database_readiness_probe(configured.database_url)

        probe = configured_database_probe

    application = FastAPI(title="Stock Agent System", version=__version__)

    @application.get("/health/live")
    def liveness() -> dict[str, str]:
        return {"status": "live"}

    @application.get("/health/ready")
    def readiness() -> dict[str, str]:
        if probe is not None:
            ready, detail = probe()
            if not ready:
                raise HTTPException(status_code=503, detail=detail)
        return {"status": "ready"}

    @application.get("/api/version")
    def version(authorization: str | None = Header(default=None)) -> dict[str, str | int]:
        expected = configured.dev_test_token
        supplied = authorization.removeprefix("Bearer ") if authorization else ""
        if not expected or not secrets.compare_digest(supplied, expected):
            raise HTTPException(status_code=401, detail="invalid development token")
        manifest = load_release_manifest(configured.release_manifest_path)
        return {
            "git_commit": configured.git_sha,
            "release_version": manifest.release_version,
            "policy_version": manifest.policy_version,
            "workflow_version": manifest.workflow_version,
            "schema_version": manifest.schema_version,
        }

    return application


app = create_app()
