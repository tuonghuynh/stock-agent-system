import ast
from pathlib import Path


def imports_in(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    return imports


def test_agents_cannot_import_execution_boundary() -> None:
    agent_root = Path("src/stock_agent/agents")
    for path in agent_root.rglob("*.py"):
        assert all(not name.startswith("stock_agent.execution") for name in imports_in(path))


def test_domain_has_no_framework_or_persistence_dependency() -> None:
    prohibited = ("fastapi", "sqlalchemy", "alembic", "psycopg")
    for path in Path("src/stock_agent/domain").rglob("*.py"):
        assert all(not name.startswith(prohibited) for name in imports_in(path))
