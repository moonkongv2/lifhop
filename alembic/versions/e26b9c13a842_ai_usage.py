"""Durable bounded AI usage reservations; no source text."""
from alembic import op
import sqlalchemy as sa

revision = "e26b9c13a842"
down_revision = "d15e8a02b731"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("ai_usage_attempts",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("billing_scope", sa.String(100), nullable=False),
        sa.Column("month", sa.String(7), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.String(32), nullable=False),
        sa.Column("purpose", sa.String(16), nullable=False),
        sa.Column("model", sa.String(64), nullable=False),
        sa.Column("configuration_hash", sa.String(64), nullable=False),
        sa.Column("input_upper_bound", sa.Integer(), nullable=False),
        sa.Column("reserved_micro_usd", sa.Integer(), nullable=False),
        sa.Column("spent_micro_usd", sa.Integer(), nullable=False),
        sa.Column("usage_tokens", sa.Integer()),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("error_code", sa.String(40)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("settled_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("reserved_micro_usd >= 0 AND spent_micro_usd >= 0 AND input_upper_bound > 0"),
        sa.CheckConstraint("status IN ('reserved','uncertain','spent','released')"))
    op.create_index("ix_ai_usage_billing_month", "ai_usage_attempts", ["billing_scope", "month"])
    op.create_index("ix_ai_usage_owner_run", "ai_usage_attempts", ["owner_id", "run_id"])


def downgrade():
    op.drop_table("ai_usage_attempts")
