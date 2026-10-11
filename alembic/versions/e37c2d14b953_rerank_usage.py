"""Retain separate input/output reservations and pricing for rerank calls."""
from alembic import op
import sqlalchemy as sa

revision = "e37c2d14b953"
down_revision = "e26b9c13a842"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("ai_usage_attempts",sa.Column("output_upper_bound",sa.Integer(),nullable=False,server_default="0"))
    for name in ("input_usage_tokens","output_usage_tokens","input_price_micro","output_price_micro"):
        op.add_column("ai_usage_attempts",sa.Column(name,sa.Integer(),nullable=True))
    op.add_column("ai_usage_attempts",sa.Column("price_hash",sa.String(64),nullable=True))


def downgrade():
    for name in ("price_hash","output_price_micro","input_price_micro","output_usage_tokens","input_usage_tokens","output_upper_bound"):
        op.drop_column("ai_usage_attempts",name)
