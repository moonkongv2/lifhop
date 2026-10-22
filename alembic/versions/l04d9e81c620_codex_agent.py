"""Source-scoped opaque credentials and durable Mac agent checkpoints."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = 'l04d9e81c620'
down_revision = 'k93c8d70b519'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('collection_subscriptions', sa.Column('agent_seen_at', sa.DateTime(timezone=True)))
    op.create_table('collector_credentials',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('subscription_id', sa.Integer(), sa.ForeignKey('collection_subscriptions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('token_hash', sa.String(64), nullable=False, unique=True),
        sa.Column('revision', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('revoked_at', sa.DateTime(timezone=True)),
        sa.Column('last_used_at', sa.DateTime(timezone=True)))
    op.create_index('ix_collector_credentials_subscription_id', 'collector_credentials', ['subscription_id'])
    op.add_column('collection_jobs', sa.Column('credential_id', sa.Integer(), sa.ForeignKey('collector_credentials.id', ondelete='SET NULL')))
    op.add_column('collection_jobs', sa.Column('checkpoint', JSONB()))


def downgrade():
    op.drop_column('collection_jobs', 'checkpoint')
    op.drop_column('collection_jobs', 'credential_id')
    op.drop_table('collector_credentials')
    op.drop_column('collection_subscriptions', 'agent_seen_at')
