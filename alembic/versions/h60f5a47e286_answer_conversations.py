"""Persist owner conversations, turns and stable source dependencies."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = 'h60f5a47e286'
down_revision = 'g59e4f36d175'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('answer_conversations',
        sa.Column('id', sa.String(length=32), primary_key=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=100), nullable=False),
        sa.Column('filters', JSONB(), nullable=False),
        sa.Column('state', sa.String(length=16), nullable=False),
        sa.Column('context_epoch', sa.Integer(), nullable=False),
        sa.Column('revision', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("state IN ('active','closed') AND revision >= 0 AND context_epoch >= 0"),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.UniqueConstraint(*['id', 'user_id']))
    op.create_index('ix_answer_conversations_owner_updated', 'answer_conversations', ['user_id', 'updated_at', 'id'], unique=False)
    op.create_table('answer_turns',
        sa.Column('id', sa.String(length=32), primary_key=True, nullable=False),
        sa.Column('conversation_id', sa.String(length=32), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('seq', sa.Integer(), nullable=False),
        sa.Column('request_id', sa.String(length=32), nullable=False),
        sa.Column('fingerprint', sa.String(length=64), nullable=False),
        sa.Column('base_revision', sa.Integer(), nullable=False),
        sa.Column('epoch', sa.Integer(), nullable=False),
        sa.Column('q', sa.Text(), nullable=False),
        sa.Column('base_turn_id', sa.String(length=32), nullable=True),
        sa.Column('evidence_reference_turn_id', sa.String(length=32), nullable=True),
        sa.Column('context_root_turn_id', sa.String(length=32), nullable=False),
        sa.Column('history_ids', JSONB(), nullable=False),
        sa.Column('resolved_q', sa.Text(), nullable=True),
        sa.Column('branch', sa.String(length=16), nullable=True),
        sa.Column('state', sa.String(length=16), nullable=False),
        sa.Column('outcome', sa.String(length=20), nullable=True),
        sa.Column('answer', sa.Text(), nullable=True),
        sa.Column('answer_status', sa.String(length=16), nullable=True),
        sa.Column('error_code', sa.String(length=64), nullable=True),
        sa.Column('redacted', sa.Boolean(), nullable=False),
        sa.Column('policy_revision', sa.Integer(), nullable=False),
        sa.Column('format_version', sa.String(length=40), nullable=False),
        sa.Column('stages', JSONB(), nullable=False),
        sa.Column('context_summary', JSONB(), nullable=False),
        sa.Column('lease_expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('action_expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("state IN ('created','planning','planned','searching','selecting','ready','answering','completed','failed','stopped','interrupted')"),
        sa.CheckConstraint("outcome IS NULL OR outcome IN ('answer','clarification','no_evidence')"),
        sa.CheckConstraint('seq > 0 AND octet_length(q) <= 2048 AND length(q) BETWEEN 1 AND 256 AND (answer IS NULL OR octet_length(answer) <= 16384) AND (resolved_q IS NULL OR octet_length(resolved_q) <= 2048)'),
        sa.ForeignKeyConstraint(['conversation_id', 'user_id'], ['answer_conversations.id', 'answer_conversations.user_id'], ondelete='CASCADE'),
        sa.UniqueConstraint(*['conversation_id', 'seq']),
        sa.UniqueConstraint(*['user_id', 'request_id']))
    op.create_index('uq_answer_turn_unfinished', 'answer_turns', ['conversation_id'], unique=True, postgresql_where=sa.text("state NOT IN ('completed','failed','stopped','interrupted')"))
    op.create_table('answer_turn_sources',
        sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('turn_id', sa.String(length=32), nullable=False),
        sa.Column('entry_id', sa.Integer(), nullable=False),
        sa.Column('version_id', sa.Integer(), nullable=False),
        sa.Column('field', sa.String(length=10), nullable=False),
        sa.Column('start', sa.Integer(), nullable=False),
        sa.Column('end', sa.Integer(), nullable=False),
        sa.Column('passage_hash', sa.String(length=64), nullable=False),
        sa.Column('projection_version', sa.String(length=40), nullable=False),
        sa.Column('direct_selected', sa.Boolean(), nullable=False),
        sa.Column('inherited', sa.Boolean(), nullable=False),
        sa.Column('dispatch_intent', sa.Boolean(), nullable=False),
        sa.Column('cited', sa.Boolean(), nullable=False),
        sa.Column('selection_order', sa.Integer(), nullable=True),
        sa.CheckConstraint('start >= 0 AND "end" > start AND "end" - start <= 2000'),
        sa.ForeignKeyConstraint(['turn_id'], ['answer_turns.id'], ondelete='CASCADE'),
        sa.UniqueConstraint(*['turn_id', 'entry_id', 'version_id', 'field', 'start', 'end', 'passage_hash', 'projection_version']))
    op.create_index('ix_answer_source_turn', 'answer_turn_sources', ['turn_id'], unique=False)
    op.create_index('ix_answer_source_version', 'answer_turn_sources', ['entry_id', 'version_id'], unique=False)


def downgrade():
    op.drop_table('answer_turn_sources')
    op.drop_table('answer_turns')
    op.drop_table('answer_conversations')
