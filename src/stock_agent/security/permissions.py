"""Immutable least-privilege role manifests and deny-by-default tool dispatch."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from enum import StrEnum
from types import MappingProxyType
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SecurityModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class AgentRole(StrEnum):
    RESEARCH = "RESEARCH"
    CRITIC = "CRITIC"
    PORTFOLIO = "PORTFOLIO"
    SINGLE_AGENT = "SINGLE_AGENT"


class PermissionManifest(SecurityModel):
    role: AgentRole
    allowed_tools: frozenset[str]
    prohibited_capabilities: frozenset[str]
    read_only: bool = True


class ToolDefinition(SecurityModel):
    name: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    allowed_roles: frozenset[AgentRole]
    parameter_schema: dict[str, type[Any]]
    read_only: bool


def default_permission_manifests() -> Mapping[AgentRole, PermissionManifest]:
    common_prohibitions = frozenset(
        {
            "broker_access",
            "credential_access",
            "account_access",
            "policy_mutation",
            "prompt_mutation",
            "tool_mutation",
            "workflow_mutation",
            "delegation",
        }
    )
    manifests = {
        AgentRole.RESEARCH: PermissionManifest(
            role=AgentRole.RESEARCH,
            allowed_tools=frozenset({"evidence_lookup"}),
            prohibited_capabilities=common_prohibitions,
        ),
        AgentRole.CRITIC: PermissionManifest(
            role=AgentRole.CRITIC,
            allowed_tools=frozenset({"evidence_lookup"}),
            prohibited_capabilities=common_prohibitions,
        ),
        AgentRole.PORTFOLIO: PermissionManifest(
            role=AgentRole.PORTFOLIO,
            allowed_tools=frozenset({"portfolio_summary", "deterministic_calculator"}),
            prohibited_capabilities=common_prohibitions,
        ),
        AgentRole.SINGLE_AGENT: PermissionManifest(
            role=AgentRole.SINGLE_AGENT,
            allowed_tools=frozenset({"evidence_lookup"}),
            prohibited_capabilities=common_prohibitions,
        ),
    }
    return MappingProxyType(manifests)


class ToolAuthorizationError(PermissionError):
    """A role requested a tool outside its immutable manifest."""


class ToolParameterError(ValueError):
    """A tool request failed strict parameter validation."""


ToolHandler = Callable[[Mapping[str, object]], object]


class DenyByDefaultToolRegistry:
    """Trusted dispatcher; absent, mutable or unauthorized tools are rejected."""

    def __init__(self, manifests: Mapping[AgentRole, PermissionManifest]) -> None:
        self._manifests = MappingProxyType(dict(manifests))
        self._tools: dict[str, tuple[ToolDefinition, ToolHandler]] = {}

    def register(self, definition: ToolDefinition, handler: ToolHandler) -> None:
        if not definition.read_only:
            raise ToolAuthorizationError("agent tools must be read-only")
        if definition.name in self._tools:
            raise ValueError("tool is already registered")
        for role in definition.allowed_roles:
            manifest = self._manifests.get(role)
            if manifest is None or definition.name not in manifest.allowed_tools:
                raise ToolAuthorizationError("tool is not allowlisted for every declared role")
        self._tools[definition.name] = (definition, handler)

    def invoke(self, role: AgentRole, name: str, parameters: Mapping[str, object]) -> object:
        manifest = self._manifests.get(role)
        registered = self._tools.get(name)
        if manifest is None or registered is None or name not in manifest.allowed_tools:
            raise ToolAuthorizationError("tool access denied by default")
        definition, handler = registered
        if role not in definition.allowed_roles or not definition.read_only:
            raise ToolAuthorizationError("tool access denied by role manifest")
        if set(parameters) != set(definition.parameter_schema):
            raise ToolParameterError("invalid tool parameters")
        validated: dict[str, object] = {}
        for key, expected_type in definition.parameter_schema.items():
            value = parameters[key]
            if type(value) is not expected_type:
                raise ToolParameterError("invalid tool parameters")
            validated[key] = value
        return handler(validated)
