"""Add owner/date pagination index and backfill proven Markdown sources.

Revision ID: f13a7b20c456
Revises: e12b6e01a123
"""
from alembic import op
import sqlalchemy as sa

revision = "f13a7b20c456"
down_revision = "e12b6e01a123"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Old entries without an artifact cannot be attributed safely.
    op.execute(sa.text("""
        UPDATE entries AS e SET provider = 'markdown'
        FROM import_artifacts AS a
        WHERE e.import_artifact_id = a.id AND e.user_id = a.user_id
          AND e.provider IS NULL AND a.mime_type = 'text/markdown'
    """))
    op.create_index("ix_entries_user_created_id", "entries", ["user_id", sa.text("created_at DESC"), sa.text("id DESC")])


def downgrade() -> None:
    op.drop_index("ix_entries_user_created_id", table_name="entries")
    # Preserve provenance: provider already existed before this migration.
