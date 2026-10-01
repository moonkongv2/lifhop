"""Add import results, retry attempts, and Entry artifact links."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "e12b6e01a123"
down_revision = "71e5e837ff01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("entries", sa.Column("import_artifact_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_entries_import_artifact_id", "entries", "import_artifacts",
        ["import_artifact_id"], ["id"], ondelete="SET NULL",
    )
    op.add_column("import_jobs", sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"))
    for name in ("entry_ids", "item_errors"):
        op.add_column("import_jobs", sa.Column(name, postgresql.JSONB(), nullable=False, server_default="[]"))
    op.create_index("ix_import_jobs_status_created_at", "import_jobs", ["status", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_import_jobs_status_created_at", table_name="import_jobs")
    for name in ("item_errors", "entry_ids", "attempts"):
        op.drop_column("import_jobs", name)
    op.drop_constraint("fk_entries_import_artifact_id", "entries", type_="foreignkey")
    op.drop_column("entries", "import_artifact_id")
