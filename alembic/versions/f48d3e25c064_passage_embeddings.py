"""Store current section vectors; preserve originals and the shared extension."""
from alembic import op
from pgvector.sqlalchemy import VECTOR
import sqlalchemy as sa

revision = "f48d3e25c064"
down_revision = "e37c2d14b953"
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    available = connection.scalar(sa.text("SELECT count(*) FROM pg_available_extensions WHERE name = 'vector'"))
    if not available:
        raise RuntimeError("pgvector server extension is unavailable. Use the pinned PostgreSQL 17 image; see SEMANTIC_PRODUCT.md.")
    installed_schema = connection.scalar(sa.text("SELECT n.nspname FROM pg_extension e JOIN pg_namespace n ON n.oid=e.extnamespace WHERE e.extname='vector'"))
    if installed_schema and installed_schema != "public":
        raise RuntimeError("pgvector must be installed in public; ask the database administrator before migrating.")
    if not installed_schema:
        try:
            connection.execute(sa.text("CREATE EXTENSION vector WITH SCHEMA public"))
        except sa.exc.DBAPIError as error:
            raise RuntimeError("An administrator must run CREATE EXTENSION vector WITH SCHEMA public before migrating.") from error
    # Keep the application's schema first while resolving the shared vector type.
    connection.execute(sa.text("SELECT set_config('search_path', quote_ident(current_schema()) || ', public', true)"))
    op.create_table("passage_embeddings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("passage_id", sa.Integer(), sa.ForeignKey("entry_passages.id", ondelete="CASCADE"), nullable=False),
        sa.Column("parent_hash", sa.String(64), nullable=False),
        sa.Column("start", sa.Integer(), nullable=False),
        sa.Column("end", sa.Integer(), nullable=False),
        sa.Column("slice_hash", sa.String(64), nullable=False),
        sa.Column("model", sa.String(80), nullable=False),
        sa.Column("config", sa.String(160), nullable=False),
        sa.Column("vector", VECTOR(1536), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("passage_id", "start", "end", "model", "config", name="uq_passage_embedding_slice"),
        sa.CheckConstraint('start >= 0 AND "end" > start AND "end" - start <= 600', name="ck_embedding_offsets"),
        sa.CheckConstraint("vector_norm(vector) > 0", name="ck_embedding_nonzero"))
    op.create_index("ix_passage_embeddings_passage", "passage_embeddings", ["passage_id"])


def downgrade():
    op.drop_table("passage_embeddings")
    # Other schemas/applications may still use public.vector.
