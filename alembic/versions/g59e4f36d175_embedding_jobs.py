"""Durable approved indexing and dispatch linkage without source bodies."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "g59e4f36d175"
down_revision = "f48d3e25c064"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("ai_usage_attempts", sa.Column("dispatch_id", sa.String(32), nullable=True))
    op.create_index("ix_ai_usage_dispatch", "ai_usage_attempts", ["dispatch_id"])
    op.create_table("embedding_runs",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("scope", sa.String(255), nullable=False),
        sa.Column("entry_ids", postgresql.JSONB(), nullable=False),
        sa.Column("scope_all", sa.Boolean(), nullable=False),
        sa.Column("follow_changes", sa.Boolean(), nullable=False),
        sa.Column("config", sa.String(160), nullable=False),
        sa.Column("manifest_digest", sa.String(64), nullable=False, unique=True),
        sa.Column("max_micro_usd", sa.Integer(), nullable=False),
        sa.Column("max_calls", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("error_code", sa.String(40), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("max_micro_usd > 0 AND max_micro_usd <= 250000 AND max_calls > 0 AND max_calls <= 5000"),
        sa.CheckConstraint("status IN ('active','paused','completed')"))
    op.create_index("ix_embedding_runs_owner", "embedding_runs", ["owner_id", "created_at"])
    op.create_table("embedding_jobs",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("run_id", sa.String(32), sa.ForeignKey("embedding_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("entry_id", sa.Integer(), nullable=False),
        sa.Column("passage_id", sa.Integer(), sa.ForeignKey("entry_passages.id", ondelete="SET NULL"), nullable=True),
        sa.Column("version_id", sa.Integer(), nullable=False),
        sa.Column("parent_hash", sa.String(64), nullable=False),
        sa.Column("start", sa.Integer(), nullable=False),
        sa.Column("end", sa.Integer(), nullable=False),
        sa.Column("slice_hash", sa.String(64), nullable=False),
        sa.Column("input_bytes", sa.Integer(), nullable=False),
        sa.Column("policy_revision", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("dispatch_id", sa.String(32), nullable=True),
        sa.Column("lease_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(40), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("run_id", "passage_id", "start", "end", name="uq_embedding_job_slice"),
        sa.CheckConstraint('start >= 0 AND "end" > start AND "end" - start <= 600 AND input_bytes > 0 AND input_bytes <= 8000'),
        sa.CheckConstraint("status IN ('pending','running','ready','blocked','stale','failed','uncertain')"))
    for name, columns in (("pending", ["status", "run_id", "created_at"]), ("entry", ["entry_id"]), ("dispatch", ["dispatch_id"])):
        op.create_index("ix_embedding_jobs_" + name, "embedding_jobs", columns)


def downgrade():
    op.drop_table("embedding_jobs")
    op.drop_table("embedding_runs")
    op.drop_index("ix_ai_usage_dispatch", table_name="ai_usage_attempts")
    op.drop_column("ai_usage_attempts", "dispatch_id")
