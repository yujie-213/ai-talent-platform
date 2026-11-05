"""Resume evidence and rebuildable index events."""
from alembic import op
import sqlalchemy as sa
revision = 'b640cc81b002'
down_revision = '95ab21c732dd'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('resume_records',
        sa.Column('task_id', sa.String(36), sa.ForeignKey('tasks.id'), primary_key=True),
        sa.Column('base_version', sa.Integer(), nullable=False),
        sa.Column('run_version', sa.Integer()),
        sa.Column('provisional', sa.Boolean(), nullable=False),
        sa.Column('batch_id', sa.String(36), nullable=False),
        sa.Column('segments', sa.JSON()), sa.Column('validated', sa.JSON()),
        sa.Column('quality', sa.String(30), nullable=False), sa.Column('model', sa.String(100)))
    op.create_index('ix_resume_records_batch_id', 'resume_records', ['batch_id'])
    op.create_table('index_events', sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('talent_id', sa.String(36), sa.ForeignKey('talents.id'), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False), sa.Column('state', sa.String(20), nullable=False),
        sa.Column('error_code', sa.String(80)), sa.UniqueConstraint('talent_id', 'version'))
    op.create_index('ix_index_events_talent_id', 'index_events', ['talent_id'])


def downgrade():
    op.drop_table('index_events')
    op.drop_table('resume_records')
