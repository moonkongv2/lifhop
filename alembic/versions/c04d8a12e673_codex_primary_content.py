"""Current Codex reading/search projection; retained evidence is unchanged."""
from alembic import op
import sqlalchemy as sa

revision = "c04d8a12e673"
down_revision = "b23c7d91e042"
branch_labels = depends_on = None


def upgrade():
    op.add_column("entries", sa.Column("primary_content", sa.Text(), nullable=True))
    # Existing v1 records have no captured phase; never guess their final answer.
    op.execute("UPDATE entries SET primary_content = content WHERE provider = 'codex'")


def downgrade():
    op.drop_column("entries", "primary_content")
