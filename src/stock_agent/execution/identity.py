"""Deterministic execution identities."""

import hashlib
import json
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from stock_agent.domain.models import OrderType, TimeInForce, TradeSide


def _decimal(value: Decimal) -> str:
    normalized = value.normalize()
    return format(normalized, "f")


def derive_idempotency_key(
    *,
    recommendation_id: UUID,
    policy_version: str,
    account_id_hash: str,
    symbol: str,
    side: TradeSide,
    target_delta: Decimal,
    order_type: OrderType,
    limit_price: Decimal,
    time_in_force: TimeInForce,
    expires_at: datetime,
) -> str:
    """Hash every immutable input that identifies a proposed broker side effect."""
    canonical = json.dumps(
        {
            "account_id_hash": account_id_hash,
            "expires_at": expires_at.isoformat(),
            "limit_price": _decimal(limit_price),
            "order_type": order_type.value,
            "policy_version": policy_version,
            "recommendation_id": str(recommendation_id),
            "side": side.value,
            "symbol": symbol,
            "target_delta": _decimal(target_delta),
            "time_in_force": time_in_force.value,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def derive_client_order_id(intent_id: UUID) -> str:
    """Return a stable broker-safe identifier derived only from the persisted intent ID."""
    return f"paper-{intent_id.hex}"
