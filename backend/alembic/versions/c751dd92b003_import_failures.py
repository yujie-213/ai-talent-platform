"""Retain invalid upload metadata for batch reconciliation."""
from alembic import op
import sqlalchemy as sa
revision = 'c751dd92b003'
down_revision = 'b640cc81b002'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('import_failures', sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('batch_id', sa.String(36), nullable=False), sa.Column('key', sa.String(128), nullable=False),
        sa.Column('request_hash', sa.String(64), nullable=False), sa.Column('name', sa.String(200), nullable=False),
        sa.Column('error_code', sa.String(80), nullable=False), sa.Column('message', sa.String(200), nullable=False),
        sa.Column('status', sa.Integer(), nullable=False), sa.UniqueConstraint('user_id', 'key'))
    op.create_index('ix_import_failures_batch_id', 'import_failures', ['batch_id'])


def downgrade():
    op.drop_table('import_failures')
