"""Persist bounded GitHub graph walks and rotating thread reconciliation."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = 'k93c8d70b519'
down_revision = 'j82b7c69a408'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('collection_subscriptions', sa.Column('discussion_selection', JSONB(), nullable=False,
        server_default=sa.text("'{\"enabled\": false, \"exclude_numbers\": []}'::jsonb")))
    op.add_column('collection_subscriptions', sa.Column('progress', JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")))
    # Existing jobs keep their frozen S1/S2 preparation and validation path.
    op.add_column('collection_jobs', sa.Column('mode', sa.String(20), nullable=False, server_default='backfill'))
    for table in ('github_commit_cursors', 'github_thread_cursors'):
        columns = [sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('subscription_id', sa.Integer(), sa.ForeignKey('collection_subscriptions.id', ondelete='CASCADE'), nullable=False),
            sa.Column('revision', sa.Integer(), nullable=False)]
        if table == 'github_commit_cursors':
            columns += [sa.Column('sha', sa.String(40), nullable=False), sa.Column('parents', JSONB(), nullable=False),
                sa.Column('ancestry_complete', sa.Boolean(), nullable=False)]
            key = 'sha'
        else:
            columns += [sa.Column('number', sa.String(20), nullable=False), sa.Column('kind', sa.String(20), nullable=False),
                sa.Column('progress', JSONB(), nullable=False), sa.Column('last_checked_at', sa.DateTime(timezone=True))]
            key = 'number'
        op.create_table(table, *columns, sa.UniqueConstraint('subscription_id', 'revision', key))
        op.create_index(f'ix_{table}_subscription_id', table, ['subscription_id'])


def downgrade():
    op.drop_table('github_thread_cursors')
    op.drop_table('github_commit_cursors')
    op.drop_column('collection_jobs', 'mode')
    op.drop_column('collection_subscriptions', 'progress')
    op.drop_column('collection_subscriptions', 'discussion_selection')
