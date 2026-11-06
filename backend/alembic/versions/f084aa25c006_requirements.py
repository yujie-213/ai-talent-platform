"""Recruitment requirement drafts and immutable confirmed versions."""
from alembic import op
import sqlalchemy as sa

revision = 'f084aa25c006'
down_revision = 'e973ff14b005'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('recruitment_requirements',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('department_id', sa.String(36), sa.ForeignKey('departments.id'), nullable=False),
        sa.Column('department_position_id', sa.String(36), sa.ForeignKey('department_positions.id'), nullable=False),
        sa.Column('created_by', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('draft', sa.JSON(), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('active_version', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.Integer(), nullable=False))
    op.create_index('ix_recruitment_requirements_department_id', 'recruitment_requirements', ['department_id'])
    op.create_table('requirement_versions',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('requirement_id', sa.String(36), sa.ForeignKey('recruitment_requirements.id'), nullable=False),
        sa.Column('number', sa.Integer(), nullable=False),
        sa.Column('snapshot', sa.JSON(), nullable=False),
        sa.Column('confirmed_by', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('created_at', sa.Integer(), nullable=False),
        sa.UniqueConstraint('requirement_id', 'number'))


def downgrade():
    op.drop_table('requirement_versions')
    # MySQL外键依赖部门索引；随整表删除，不能先单独删除该索引。
    op.drop_table('recruitment_requirements')
