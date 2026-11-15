"""Deterministic freshness validation for authorization inputs."""

from dataclasses import dataclass
from datetime import datetime, timedelta

from stock_agent.domain.models import RiskCheck
from stock_agent.policy.models import FreshnessPolicy


@dataclass(frozen=True, slots=True)
class RiskDataTimestamps:
    quote: datetime | None
    position: datetime | None
    pending_orders: datetime | None
    account: datetime | None
    buying_power: datetime | None


def freshness_checks(
    timestamps: RiskDataTimestamps,
    *,
    evaluated_at: datetime,
    policy: FreshnessPolicy,
) -> tuple[RiskCheck, ...]:
    """Return a named check for every material risk input."""
    limits = (
        ("QUOTE", timestamps.quote, policy.execution_quote_seconds),
        ("POSITION", timestamps.position, policy.positions_snapshot_seconds),
        ("PENDING-ORDERS", timestamps.pending_orders, policy.pending_orders_snapshot_seconds),
        ("ACCOUNT", timestamps.account, policy.account_snapshot_seconds),
        ("BUYING-POWER", timestamps.buying_power, policy.account_snapshot_seconds),
    )
    checks: list[RiskCheck] = []
    for name, observed_at, maximum_seconds in limits:
        age = evaluated_at - observed_at if observed_at is not None else None
        passed = (
            age is not None
            and timedelta(0) <= age <= timedelta(seconds=maximum_seconds)
        )
        checks.append(
            RiskCheck(
                rule_id=f"RSK-FRESHNESS-{name}",
                passed=passed,
                observed_value=(f"{age.total_seconds():.6f}s" if age is not None else "MISSING"),
                limit_value=f"{maximum_seconds}s",
                reason=(
                    f"{name.lower()} snapshot is fresh"
                    if passed
                    else f"{name.lower()} snapshot is stale or from the future"
                ),
                evidence_timestamp=observed_at or evaluated_at,
            )
        )
    return tuple(checks)
