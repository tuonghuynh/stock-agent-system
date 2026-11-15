from types import MappingProxyType

import pytest
from pydantic import ValidationError

from stock_agent.security.permissions import (
    AgentRole,
    DenyByDefaultToolRegistry,
    ToolAuthorizationError,
    ToolDefinition,
    ToolParameterError,
    default_permission_manifests,
)


def registry() -> DenyByDefaultToolRegistry:
    manifests = default_permission_manifests()
    tools = DenyByDefaultToolRegistry(manifests)
    tools.register(
        ToolDefinition(
            name="evidence_lookup",
            allowed_roles=frozenset({AgentRole.RESEARCH, AgentRole.CRITIC}),
            parameter_schema={"symbol": str, "as_of": str},
            read_only=True,
        ),
        lambda parameters: MappingProxyType(dict(parameters)),
    )
    return tools


def test_sec001_permissions_are_immutable_and_least_privilege() -> None:
    manifests = default_permission_manifests()
    for role, manifest in manifests.items():
        assert manifest.role is role
        assert manifest.read_only
        assert {
            "broker_access",
            "credential_access",
            "policy_mutation",
            "prompt_mutation",
            "tool_mutation",
            "workflow_mutation",
            "delegation",
        }.issubset(manifest.prohibited_capabilities)
        assert all("broker" not in tool for tool in manifest.allowed_tools)
    with pytest.raises(TypeError):
        manifests[AgentRole.RESEARCH] = manifests[AgentRole.CRITIC]  # type: ignore[index]
    with pytest.raises(ValidationError):
        manifests[AgentRole.RESEARCH].read_only = False  # type: ignore[misc]


def test_sec002_tool_registry_denies_unknown_role_tool_and_mutation() -> None:
    tools = registry()
    result = tools.invoke(
        AgentRole.RESEARCH,
        "evidence_lookup",
        {"symbol": "AAPL", "as_of": "2026-11-14T20:00:00Z"},
    )
    assert result["symbol"] == "AAPL"  # type: ignore[index]
    with pytest.raises(ToolAuthorizationError, match="denied"):
        tools.invoke(AgentRole.PORTFOLIO, "evidence_lookup", {"symbol": "AAPL"})
    with pytest.raises(ToolAuthorizationError, match="denied"):
        tools.invoke(AgentRole.RESEARCH, "submit_order", {"symbol": "AAPL"})
    with pytest.raises(ToolAuthorizationError, match="read-only"):
        tools.register(
            ToolDefinition(
                name="policy_write",
                allowed_roles=frozenset({AgentRole.RESEARCH}),
                parameter_schema={"version": str},
                read_only=False,
            ),
            lambda parameters: parameters,
        )


def test_sec002_tool_parameters_are_strict_and_reject_unknown_fields() -> None:
    tools = registry()
    with pytest.raises(ToolParameterError, match="invalid"):
        tools.invoke(
            AgentRole.RESEARCH,
            "evidence_lookup",
            {"symbol": 123, "as_of": "2026-11-14", "account_id": "unexpected"},
        )
