from contextlib import redirect_stdout
from pathlib import Path

from alembic import command
from alembic.config import Config


def test_initial_alembic_migration_compiles_for_postgresql(tmp_path: Path) -> None:
    output = tmp_path / "migration.sql"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", "postgresql+psycopg://unused")
    with output.open("w", encoding="utf-8") as stream, redirect_stdout(stream):
        command.upgrade(config, "head", sql=True)
    sql = output.read_text(encoding="utf-8")
    assert "CREATE TABLE policy_version" in sql
    assert "CREATE TABLE trade_intent" in sql
    assert "CREATE TABLE audit_event" in sql
    assert "environment = 'PAPER'" in sql
