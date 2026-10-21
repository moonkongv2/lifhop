"""Paused-by-default collection schedules and bounded job retries."""
from alembic import op
import sqlalchemy as sa

revision = 'j82b7c69a408'
down_revision = 'i71a6b58f397'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('collection_subscriptions', sa.Column('schedule_enabled', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('collection_subscriptions', sa.Column('interval_seconds', sa.Integer(), nullable=False, server_default='900'))
    op.add_column('collection_subscriptions', sa.Column('next_due_at', sa.DateTime(timezone=True)))
    op.add_column('collection_subscriptions', sa.Column('schedule_error', sa.String(60)))
    op.create_check_constraint('ck_collection_interval', 'collection_subscriptions', 'interval_seconds BETWEEN 60 AND 604800')
    op.add_column('collection_jobs', sa.Column('scheduled_for', sa.DateTime(timezone=True)))
    op.add_column('collection_jobs', sa.Column('attempts', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('collection_jobs', sa.Column('retry_at', sa.DateTime(timezone=True)))
    op.create_unique_constraint('uq_collection_scheduled_slot', 'collection_jobs', ['subscription_id', 'scheduled_for'])


def downgrade():
    op.drop_constraint('uq_collection_scheduled_slot', 'collection_jobs')
    for column in ('retry_at', 'attempts', 'scheduled_for'):
        op.drop_column('collection_jobs', column)
    op.drop_constraint('ck_collection_interval', 'collection_subscriptions')
    for column in ('schedule_error', 'next_due_at', 'interval_seconds', 'schedule_enabled'):
        op.drop_column('collection_subscriptions', column)
