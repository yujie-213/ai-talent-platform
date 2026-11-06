"""Independent full-scope matching tasks, snapshots and explicit applications."""
from alembic import op
import sqlalchemy as sa
revision = 'g195bb36d007'
down_revision = 'f084aa25c006'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('match_runs',
        sa.Column('id', sa.String(36), primary_key=True, nullable=False),
        sa.Column('requirement_id', sa.String(36), sa.ForeignKey('recruitment_requirements.id'), nullable=False),
        sa.Column('requirement_version', sa.Integer(), nullable=False),
        sa.Column('created_by', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('requirement_snapshot', sa.JSON(), nullable=False),
        sa.Column('scope_snapshot', sa.JSON(), nullable=False),
        sa.Column('rules', sa.JSON(), nullable=False),
        sa.Column('state', sa.String(20), nullable=False),
        sa.Column('outcome', sa.String(20), nullable=True),
        sa.Column('run_version', sa.Integer(), nullable=False),
        sa.Column('lease_until', sa.Integer(), nullable=True),
        sa.Column('error_code', sa.String(80), nullable=True),
        sa.Column('created_at', sa.Integer(), nullable=False))
    op.create_table('match_entries',
        sa.Column('id', sa.String(36), primary_key=True, nullable=False),
        sa.Column('run_id', sa.String(36), sa.ForeignKey('match_runs.id'), nullable=False),
        sa.Column('talent_id', sa.String(36), sa.ForeignKey('talents.id'), nullable=False),
        sa.Column('snapshot', sa.JSON(), nullable=False),
        sa.Column('lexical_score', sa.Float(), nullable=False),
        sa.Column('state', sa.String(20), nullable=False),
        sa.Column('result', sa.JSON(), nullable=True),
        sa.Column('error_code', sa.String(80), nullable=True),
        sa.UniqueConstraint('run_id', 'talent_id'))
    op.create_table('match_attempts',
        sa.Column('id', sa.String(36), primary_key=True, nullable=False),
        sa.Column('run_id', sa.String(36), sa.ForeignKey('match_runs.id'), nullable=False),
        sa.Column('run_version', sa.Integer(), nullable=False),
        sa.Column('state', sa.String(20), nullable=False),
        sa.Column('started_at', sa.Integer(), nullable=False),
        sa.Column('ended_at', sa.Integer(), nullable=True),
        sa.UniqueConstraint('run_id', 'run_version'))
    op.create_table('match_outbox',
        sa.Column('id', sa.String(36), primary_key=True, nullable=False),
        sa.Column('run_id', sa.String(36), sa.ForeignKey('match_runs.id'), nullable=False),
        sa.Column('run_version', sa.Integer(), nullable=False),
        sa.Column('published_at', sa.Integer(), nullable=True),
        sa.Column('tries', sa.Integer(), nullable=False),
        sa.UniqueConstraint('run_id', 'run_version'))
    op.create_table('talent_requirements',
        sa.Column('talent_id', sa.String(36), sa.ForeignKey('talents.id'), primary_key=True, nullable=False),
        sa.Column('requirement_id', sa.String(36), sa.ForeignKey('recruitment_requirements.id'), primary_key=True, nullable=False),
        sa.Column('created_by', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('created_at', sa.Integer(), nullable=False))
    op.create_index('ix_match_runs_requirement_id', 'match_runs', ['requirement_id'])
    op.create_index('ix_match_entries_run_id', 'match_entries', ['run_id'])
    op.create_index('ix_match_outbox_published_at', 'match_outbox', ['published_at'])


def downgrade():
    op.drop_table('talent_requirements')
    op.drop_table('match_outbox')
    op.drop_table('match_attempts')
    op.drop_table('match_entries')
    op.drop_table('match_runs')
