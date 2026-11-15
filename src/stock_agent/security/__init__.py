"""Defense-in-depth controls for agent permissions and security validation."""

from stock_agent.security.architecture import ArchitectureViolation, inspect_agent_boundary
from stock_agent.security.configuration import RuntimeSecurityConfig, validate_runtime_security
from stock_agent.security.injection import AdversarialContentScanner, ThreatDisposition
from stock_agent.security.permissions import (
    AgentRole,
    DenyByDefaultToolRegistry,
    PermissionManifest,
    ToolDefinition,
    default_permission_manifests,
)
from stock_agent.security.trace import SecureTraceAssertion, assert_secure_trace

__all__ = [
    "AdversarialContentScanner",
    "AgentRole",
    "ArchitectureViolation",
    "DenyByDefaultToolRegistry",
    "PermissionManifest",
    "RuntimeSecurityConfig",
    "SecureTraceAssertion",
    "ThreatDisposition",
    "ToolDefinition",
    "assert_secure_trace",
    "default_permission_manifests",
    "inspect_agent_boundary",
    "validate_runtime_security",
]
