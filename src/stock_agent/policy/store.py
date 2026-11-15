import hashlib
import json
from dataclasses import dataclass
from typing import Any

import sqlalchemy as sa
from sqlalchemy.engine import Connection

from stock_agent.database import Base
from stock_agent.policy.models import PolicyDocument

policy_version_table = sa.Table(
    "policy_version",
    Base.metadata,
    sa.Column("policy_id", sa.String(128), primary_key=True),
    sa.Column("version", sa.Integer, primary_key=True),
    sa.Column("effective_from", sa.Date, nullable=False),
    sa.Column("content", sa.JSON, nullable=False),
    sa.Column("content_hash", sa.String(64), nullable=False, unique=True),
    sa.Column(
        "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    ),
)


@dataclass(frozen=True)
class StoredPolicy:
    policy_id: str
    version: int
    content_hash: str


class PolicyVersionStore:
    def persist_immutable(self, connection: Connection, policy: PolicyDocument) -> StoredPolicy:
        content = policy.model_dump(mode="json")
        digest = self.content_hash(content)
        existing = connection.execute(
            sa.select(policy_version_table.c.content_hash).where(
                policy_version_table.c.policy_id == policy.policy_id,
                policy_version_table.c.version == policy.version,
            )
        ).scalar_one_or_none()
        if existing is not None:
            if existing != digest:
                raise ValueError("policy version is immutable and has different content")
            return StoredPolicy(policy.policy_id, policy.version, digest)
        connection.execute(
            policy_version_table.insert().values(
                policy_id=policy.policy_id,
                version=policy.version,
                effective_from=policy.effective_from,
                content=content,
                content_hash=digest,
            )
        )
        return StoredPolicy(policy.policy_id, policy.version, digest)

    @staticmethod
    def content_hash(content: dict[str, Any]) -> str:
        canonical = json.dumps(content, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        return hashlib.sha256(canonical.encode()).hexdigest()
