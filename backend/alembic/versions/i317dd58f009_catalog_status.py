"""Retire catalog entries without deleting historical ownership."""
from alembic import op
import sqlalchemy as sa
revision = 'i317dd58f009'
down_revision = 'h206cc47e008'
branch_labels = None
depends_on = None


def upgrade():
    for table in ('departments', 'positions', 'pools', 'department_positions'):
        op.add_column(table, sa.Column('enabled', sa.Boolean(), nullable=False, server_default=sa.true()))
        op.add_column(table, sa.Column('version', sa.Integer(), nullable=False, server_default='1'))


def downgrade():
    for table in ('department_positions', 'pools', 'positions', 'departments'):
        op.drop_column(table, 'version')
        op.drop_column(table, 'enabled')
