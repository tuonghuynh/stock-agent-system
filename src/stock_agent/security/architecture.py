"""Static capability inspection for the untrusted agent package boundary."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ArchitectureViolation:
    path: str
    line: int
    capability: str


_PROHIBITED_IMPORTS = (
    "stock_agent.execution",
    "stock_agent.database",
    "stock_agent.policy.store",
    "psycopg",
    "sqlalchemy",
)
_PROHIBITED_NAMES = frozenset(
    {
        "BrokerAdapter",
        "AlpacaPaperAdapter",
        "ExecutionService",
        "PolicyVersionStore",
        "database_url",
        "credentials",
        "api_key",
    }
)


def inspect_agent_boundary(root: Path) -> tuple[ArchitectureViolation, ...]:
    violations: list[ArchitectureViolation] = []
    for path in sorted(root.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith(_PROHIBITED_IMPORTS):
                        violations.append(
                            ArchitectureViolation(str(path), node.lineno, alias.name)
                        )
            elif isinstance(node, ast.ImportFrom) and node.module:
                if node.module.startswith(_PROHIBITED_IMPORTS):
                    violations.append(
                        ArchitectureViolation(str(path), node.lineno, node.module)
                    )
                for alias in node.names:
                    if alias.name in _PROHIBITED_NAMES:
                        violations.append(
                            ArchitectureViolation(str(path), node.lineno, alias.name)
                        )
            elif isinstance(node, ast.Name) and node.id in _PROHIBITED_NAMES:
                violations.append(ArchitectureViolation(str(path), node.lineno, node.id))
    return tuple(violations)
