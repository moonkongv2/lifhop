"""Source-bound GitHub collect-now requests and fenced worker leases."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = 'i71a6b58f397'
down_revision = 'h60f5a47e286'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('collection_subscriptions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('provider', sa.String(50), nullable=False),
        sa.Column('scope', sa.String(255), nullable=False),
        sa.Column('config', JSONB(), nullable=False),
        sa.Column('revision', sa.Integer(), nullable=False),
        sa.Column('last_checked_at', sa.DateTime(timezone=True)),
        sa.Column('last_success_at', sa.DateTime(timezone=True)),
        sa.UniqueConstraint('user_id', 'provider', 'scope'))
    op.create_table('collection_jobs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('subscription_id', sa.Integer(), sa.ForeignKey('collection_subscriptions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('request_id', sa.String(36), nullable=False),
        sa.Column('revision', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('generation', sa.Integer(), nullable=False),
        sa.Column('lease_owner', sa.String(36)),
        sa.Column('lease_until', sa.DateTime(timezone=True)),
        sa.Column('run_id', sa.Integer(), sa.ForeignKey('collection_runs.id', ondelete='SET NULL')),
        sa.Column('error_code', sa.String(60)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('finished_at', sa.DateTime(timezone=True)),
        sa.UniqueConstraint('subscription_id', 'request_id'))
    op.create_index('ix_collection_jobs_subscription_id', 'collection_jobs', ['subscription_id'])
    op.create_index('uq_collection_job_active', 'collection_jobs', ['subscription_id'], unique=True,
                    postgresql_where=sa.text("status IN ('pending','running')"))

    op.create_table('collection_requests',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('subscription_id', sa.Integer(), sa.ForeignKey('collection_subscriptions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('request_id', sa.String(36), nullable=False),
        sa.Column('job_id', sa.Integer(), sa.ForeignKey('collection_jobs.id', ondelete='CASCADE'), nullable=False),
        sa.UniqueConstraint('subscription_id', 'request_id'))


def downgrade():
    op.drop_table('collection_requests')
    op.drop_table('collection_jobs')
    op.drop_table('collection_subscriptions')
