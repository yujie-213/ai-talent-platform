"""Durable archive chat, graph checkpoints and safe AI metadata."""
from alembic import op
import sqlalchemy as sa
revision = 'j428ee69a010'
down_revision = 'i317dd58f009'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('chat_conversations',
        sa.Column('id', sa.String(36), nullable=False, primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False, primary_key=False),
        sa.Column('scope', sa.JSON(), nullable=False, primary_key=False),
        sa.Column('conditions', sa.JSON(), nullable=False, primary_key=False),
        sa.Column('pending', sa.JSON(), nullable=True, primary_key=False),
        sa.Column('version', sa.Integer(), nullable=False, primary_key=False),
        sa.Column('created_at', sa.Integer(), nullable=False, primary_key=False))
    op.create_index('ix_chat_conversations_user_id', 'chat_conversations', ['user_id'])
    op.create_table('chat_messages',
        sa.Column('id', sa.String(36), nullable=False, primary_key=True),
        sa.Column('conversation_id', sa.String(36), sa.ForeignKey('chat_conversations.id'), nullable=False, primary_key=False),
        sa.Column('sequence', sa.Integer(), nullable=False),
        sa.Column('question', sa.Text(), nullable=False, primary_key=False),
        sa.Column('scope', sa.JSON(), nullable=False, primary_key=False),
        sa.Column('plan', sa.JSON(), nullable=True, primary_key=False),
        sa.Column('answer', sa.JSON(), nullable=True, primary_key=False),
        sa.Column('created_at', sa.Integer(), nullable=False, primary_key=False),
        sa.UniqueConstraint('conversation_id','sequence'))
    op.create_index('ix_chat_messages_conversation_id', 'chat_messages', ['conversation_id'])
    op.create_table('chat_jobs',
        sa.Column('id', sa.String(36), nullable=False, primary_key=True),
        sa.Column('message_id', sa.String(36), sa.ForeignKey('chat_messages.id'), nullable=False, primary_key=False),
        sa.Column('state', sa.String(20), nullable=False, primary_key=False),
        sa.Column('run_version', sa.Integer(), nullable=False, primary_key=False),
        sa.Column('lease_until', sa.Integer(), nullable=True, primary_key=False),
        sa.Column('error_code', sa.String(80), nullable=True, primary_key=False),
        sa.UniqueConstraint('message_id'))
    op.create_table('chat_entries',
        sa.Column('id', sa.String(36), nullable=False, primary_key=True),
        sa.Column('job_id', sa.String(36), sa.ForeignKey('chat_jobs.id'), nullable=False, primary_key=False),
        sa.Column('talent_id', sa.String(36), sa.ForeignKey('talents.id'), nullable=False, primary_key=False),
        sa.Column('snapshot', sa.JSON(), nullable=False, primary_key=False),
        sa.Column('state', sa.String(20), nullable=False, primary_key=False),
        sa.Column('result', sa.JSON(), nullable=True, primary_key=False),
        sa.Column('error_code', sa.String(80), nullable=True, primary_key=False),
        sa.UniqueConstraint('job_id', 'talent_id'))
    op.create_index('ix_chat_entries_job_id', 'chat_entries', ['job_id'])
    op.create_table('chat_attempts',
        sa.Column('id', sa.String(36), nullable=False, primary_key=True),
        sa.Column('job_id', sa.String(36), sa.ForeignKey('chat_jobs.id'), nullable=False, primary_key=False),
        sa.Column('run_version', sa.Integer(), nullable=False, primary_key=False),
        sa.Column('state', sa.String(20), nullable=False, primary_key=False),
        sa.Column('started_at', sa.Integer(), nullable=False, primary_key=False),
        sa.Column('ended_at', sa.Integer(), nullable=True, primary_key=False),
        sa.UniqueConstraint('job_id', 'run_version'))
    op.create_table('chat_outbox',
        sa.Column('id', sa.String(36), nullable=False, primary_key=True),
        sa.Column('job_id', sa.String(36), sa.ForeignKey('chat_jobs.id'), nullable=False, primary_key=False),
        sa.Column('run_version', sa.Integer(), nullable=False, primary_key=False),
        sa.Column('published_at', sa.Integer(), nullable=True, primary_key=False),
        sa.Column('tries', sa.Integer(), nullable=False, primary_key=False),
        sa.UniqueConstraint('job_id', 'run_version'))
    op.create_table('chat_checkpoints',
        sa.Column('id', sa.String(36), nullable=False, primary_key=True),
        sa.Column('job_id', sa.String(36), sa.ForeignKey('chat_jobs.id'), nullable=False, primary_key=False),
        sa.Column('run_version', sa.Integer(), nullable=False, primary_key=False),
        sa.Column('checkpoint_id', sa.String(80), nullable=False, primary_key=False),
        sa.Column('parent_id', sa.String(80), nullable=True, primary_key=False),
        sa.Column('checkpoint', sa.JSON(), nullable=False, primary_key=False),
        sa.Column('checkpoint_metadata', sa.JSON(), nullable=False, primary_key=False),
        sa.Column('writes', sa.JSON(), nullable=False, primary_key=False),
        sa.UniqueConstraint('job_id', 'run_version', 'checkpoint_id'))
    op.create_table('ai_calls',
        sa.Column('id', sa.String(36), nullable=False, primary_key=True),
        sa.Column('operation', sa.String(50), nullable=False, primary_key=False),
        sa.Column('target_id', sa.String(80), nullable=True, primary_key=False),
        sa.Column('model', sa.String(100), nullable=False, primary_key=False),
        sa.Column('state', sa.String(20), nullable=False, primary_key=False),
        sa.Column('elapsed_ms', sa.Integer(), nullable=False, primary_key=False),
        sa.Column('error_code', sa.String(80), nullable=True, primary_key=False),
        sa.Column('created_at', sa.Integer(), nullable=False, primary_key=False))
    op.create_index('ix_ai_calls_created_at', 'ai_calls', ['created_at'])

def downgrade():
    for table in ['ai_calls', 'chat_checkpoints', 'chat_outbox', 'chat_attempts', 'chat_entries', 'chat_jobs', 'chat_messages', 'chat_conversations']:
        op.drop_table(table)
