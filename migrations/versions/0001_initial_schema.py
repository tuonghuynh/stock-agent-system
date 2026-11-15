"""Initial durable paper-trading schema."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "policy_version",
        sa.Column("policy_id", sa.String(128), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("content", postgresql.JSONB(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("policy_id", "version"),
        sa.CheckConstraint("version > 0", name="ck_policy_version_positive"),
    )
    op.create_table(
        "release_manifest",
        sa.Column("release_version", sa.String(128), primary_key=True),
        sa.Column("workflow_version", sa.String(128), nullable=False),
        sa.Column("schema_version", sa.String(128), nullable=False),
        sa.Column("policy_id", sa.String(128), nullable=False),
        sa.Column("policy_version", sa.Integer(), nullable=False),
        sa.Column("content", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["policy_id", "policy_version"], ["policy_version.policy_id", "policy_version.version"]
        ),
    )
    op.create_table(
        "decision_run",
        sa.Column("run_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("trace_id", sa.String(128), nullable=False, unique=True),
        sa.Column("objective", sa.Text(), nullable=False),
        sa.Column("symbols", postgresql.JSONB(), nullable=False),
        sa.Column("horizon", sa.String(64), nullable=False),
        sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
        sa.Column("policy_id", sa.String(128), nullable=False),
        sa.Column("policy_version", sa.Integer(), nullable=False),
        sa.Column("release_version", sa.String(128), sa.ForeignKey("release_manifest.release_version"), nullable=False),
        sa.Column("workflow_version", sa.String(128), nullable=False),
        sa.Column("manifest", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["policy_id", "policy_version"], ["policy_version.policy_id", "policy_version.version"]
        ),
    )
    op.create_table(
        "evidence_snapshot",
        sa.Column("snapshot_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("decision_run.run_id"), unique=True, nullable=False),
        sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
        sa.Column("content_hash", sa.String(64), unique=True, nullable=False),
        sa.Column("entries", postgresql.JSONB(), nullable=False),
    )
    op.create_table(
        "recommendation",
        sa.Column("recommendation_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("decision_run.run_id"), nullable=False),
        sa.Column("variant", sa.String(32), nullable=False),
        sa.Column("symbol", sa.String(16), nullable=False),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("policy_version", sa.String(128), nullable=False),
        sa.Column("release_version", sa.String(128), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("confidence", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.UniqueConstraint("run_id", "variant", "symbol"),
        sa.CheckConstraint("confidence between 0 and 100", name="ck_recommendation_confidence"),
    )
    op.create_table(
        "risk_decision",
        sa.Column("risk_decision_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("recommendation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("recommendation.recommendation_id"), unique=True, nullable=False),
        sa.Column("policy_version", sa.String(128), nullable=False),
        sa.Column("account_snapshot_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decision", sa.String(16), nullable=False),
        sa.Column("checks", postgresql.JSONB(), nullable=False),
    )
    op.create_table(
        "trade_intent",
        sa.Column("intent_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("idempotency_key", sa.String(64), unique=True, nullable=False),
        sa.Column("recommendation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("recommendation.recommendation_id"), nullable=False),
        sa.Column("risk_decision_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("risk_decision.risk_decision_id"), nullable=False),
        sa.Column("environment", sa.String(16), nullable=False),
        sa.Column("symbol", sa.String(16), nullable=False),
        sa.Column("side", sa.String(8), nullable=False),
        sa.Column("quantity", sa.Numeric(24, 8), nullable=False),
        sa.Column("order_type", sa.String(16), nullable=False),
        sa.Column("limit_price", sa.Numeric(24, 8), nullable=False),
        sa.Column("time_in_force", sa.String(8), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("policy_version", sa.String(128), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("environment = 'PAPER'", name="ck_intent_paper_only"),
        sa.CheckConstraint("order_type = 'LIMIT'", name="ck_intent_limit_only"),
        sa.CheckConstraint("time_in_force = 'DAY'", name="ck_intent_day_only"),
    )
    op.create_table(
        "broker_order",
        sa.Column("order_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("intent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("trade_intent.intent_id"), nullable=False),
        sa.Column("broker_order_id", sa.String(128)),
        sa.Column("client_order_id", sa.String(128), unique=True, nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("requested_quantity", sa.Numeric(24, 8), nullable=False),
        sa.Column("filled_quantity", sa.Numeric(24, 8), server_default="0", nullable=False),
        sa.Column("average_fill_price", sa.Numeric(24, 8)),
        sa.Column("raw_response_hash", sa.String(64)),
        sa.Column("submitted_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "fill",
        sa.Column("fill_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("broker_order.order_id"), nullable=False),
        sa.Column("broker_fill_id", sa.String(128), nullable=False),
        sa.Column("quantity", sa.Numeric(24, 8), nullable=False),
        sa.Column("price", sa.Numeric(24, 8), nullable=False),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deduplication_hash", sa.String(64), unique=True, nullable=False),
        sa.UniqueConstraint("order_id", "broker_fill_id"),
    )
    op.create_table(
        "reservation",
        sa.Column("reservation_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("intent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("trade_intent.intent_id"), unique=True, nullable=False),
        sa.Column("account_id_hash", sa.String(64), nullable=False),
        sa.Column("symbol", sa.String(16), nullable=False),
        sa.Column("cash_amount", sa.Numeric(24, 8), server_default="0", nullable=False),
        sa.Column("share_quantity", sa.Numeric(24, 8), server_default="0", nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
    )
    op.create_table(
        "workflow_checkpoint",
        sa.Column("checkpoint_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("decision_run.run_id"), nullable=False),
        sa.Column("step", sa.String(64), nullable=False),
        sa.Column("state", postgresql.JSONB(), nullable=False),
        sa.Column("claimed_by", sa.String(128)),
        sa.Column("claim_expires_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("run_id", "step"),
    )
    op.create_table(
        "audit_event",
        sa.Column("event_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("trace_id", sa.String(128), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("decision_run.run_id")),
        sa.Column("intent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("trade_intent.intent_id")),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("component", sa.String(64), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor_type", sa.String(64), nullable=False),
        sa.Column("actor_version", sa.String(128), nullable=False),
        sa.Column("input_references", postgresql.JSONB(), nullable=False),
        sa.Column("output_references", postgresql.JSONB(), nullable=False),
        sa.Column("redacted_metadata", postgresql.JSONB(), nullable=False),
    )
    op.create_index("ix_audit_trace", "audit_event", ["trace_id", "occurred_at"])
    op.create_index("ix_intent_status", "trade_intent", ["status", "updated_at"])


def downgrade() -> None:
    for table in (
        "audit_event", "workflow_checkpoint", "reservation", "fill", "broker_order",
        "trade_intent", "risk_decision", "recommendation", "evidence_snapshot",
        "decision_run", "release_manifest", "policy_version",
    ):
        op.drop_table(table)
