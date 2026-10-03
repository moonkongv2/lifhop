"""Durable Codex collection receipts without duplicate content storage."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "b23c7d91e042"
down_revision = "a22b8c30d567"
branch_labels = depends_on = None


def upgrade():
    op.create_table("collection_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("client_run_uuid", sa.String(36), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False), sa.Column("scope", sa.String(255), nullable=False),
        sa.Column("manifest_digest", sa.String(64), nullable=False),
        sa.Column("parser_version", sa.String(100), nullable=False), sa.Column("filter_version", sa.String(100), nullable=False),
        sa.Column("expected_items", sa.Integer(), nullable=False), sa.Column("coverage", JSONB, nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True)), sa.UniqueConstraint("user_id", "client_run_uuid"))
    op.create_index("ix_collection_runs_user_id", "collection_runs", ["user_id"])
    op.create_table("collection_run_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("run_id", sa.Integer(), sa.ForeignKey("collection_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("external_id", sa.String(255), nullable=False), sa.Column("payload_digest", sa.String(64), nullable=False),
        sa.Column("outcome", sa.String(20), nullable=False), sa.Column("error_code", sa.String(60)),
        sa.UniqueConstraint("run_id", "external_id"))
    op.create_index("ix_collection_run_items_run_id", "collection_run_items", ["run_id"])


def downgrade():
    op.drop_table("collection_run_items")
    op.drop_table("collection_runs")
