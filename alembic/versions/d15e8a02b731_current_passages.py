"""Current-version passages and resumable projection state."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "d15e8a02b731"
down_revision = "c04d8a12e673"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("entry_passages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("version_id", sa.Integer(), sa.ForeignKey("entry_versions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("field", sa.String(10), nullable=False),
        sa.Column("start", sa.Integer(), nullable=False),
        sa.Column("end", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("passage_hash", sa.String(64), nullable=False),
        sa.Column("projection_version", sa.String(40), nullable=False),
        sa.Column("work_only", sa.Boolean(), nullable=False),
        sa.Column("group_key", sa.String(64)),
        sa.Column("search_vector", postgresql.TSVECTOR(), sa.Computed("to_tsvector('simple'::regconfig, text)", persisted=True), nullable=False),
        sa.UniqueConstraint("version_id", "projection_version", "ordinal"),
        sa.CheckConstraint("start >= 0 AND \"end\" > start AND length(text) = \"end\" - start", name="ck_passage_offsets"),
    )
    op.create_index("ix_passages_version_ordinal", "entry_passages", ["version_id", "ordinal"])
    op.create_index("ix_passages_search_vector", "entry_passages", ["search_vector"], postgresql_using="gin")
    op.create_index("ix_passages_group", "entry_passages", ["group_key"])
    op.create_table("passage_index_states",
        sa.Column("entry_id", sa.Integer(), sa.ForeignKey("entries.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("indexed_version_id", sa.Integer(), sa.ForeignKey("entry_versions.id", ondelete="CASCADE")),
        sa.Column("projection_version", sa.String(40), nullable=False),
        sa.Column("content_hash", sa.String(64)),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("passage_count", sa.Integer(), nullable=False),
        sa.Column("gap_codes", sa.String(200), nullable=False),
        sa.Column("indexed_at", sa.DateTime(timezone=True)),
    )
    op.execute("INSERT INTO passage_index_states (entry_id,projection_version,status,passage_count,gap_codes) SELECT id,'pending','pending',0,'' FROM entries")


def downgrade():
    op.drop_table("passage_index_states")
    op.drop_table("entry_passages")
