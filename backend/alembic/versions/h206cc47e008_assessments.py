"""Immutable assessment papers, locked submissions and unique results."""
from alembic import op
import sqlalchemy as sa

revision = 'h206cc47e008'
down_revision = 'g195bb36d007'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('assessment_questions',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False),
        sa.Column('content', sa.JSON(), nullable=False))
    op.create_table('assessment_papers',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('title', sa.String(100), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False))
    op.create_table('assessment_paper_versions',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('paper_id', sa.String(36), sa.ForeignKey('assessment_papers.id'), nullable=False),
        sa.Column('number', sa.Integer(), nullable=False),
        sa.Column('snapshot', sa.JSON(), nullable=False),
        sa.Column('created_by', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('created_at', sa.Integer(), nullable=False),
        sa.UniqueConstraint('paper_id', 'number'))
    op.create_table('assessment_assignments',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('paper_version_id', sa.String(36), sa.ForeignKey('assessment_paper_versions.id'), nullable=False),
        sa.Column('employee_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('talent_id', sa.String(36), sa.ForeignKey('talents.id'), nullable=False),
        sa.Column('assigned_by', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('state', sa.String(20), nullable=False),
        sa.Column('draft', sa.JSON(), nullable=False),
        sa.Column('final_answers', sa.JSON(), nullable=True),
        sa.Column('submitted_at', sa.Integer(), nullable=True),
        sa.Column('error_code', sa.String(80), nullable=True),
        sa.Column('created_at', sa.Integer(), nullable=False))
    op.create_index('ix_assessment_assignments_employee_id', 'assessment_assignments', ['employee_id'])
    op.create_index('ix_assessment_assignments_talent_id', 'assessment_assignments', ['talent_id'])
    op.create_table('assessment_results',
        sa.Column('assignment_id', sa.String(36), sa.ForeignKey('assessment_assignments.id'), primary_key=True),
        sa.Column('total', sa.Integer(), nullable=False),
        sa.Column('maximum', sa.Integer(), nullable=False),
        sa.Column('dimensions', sa.JSON(), nullable=False),
        sa.Column('rules_version', sa.String(40), nullable=False),
        sa.Column('created_at', sa.Integer(), nullable=False))


def downgrade():
    for name in ('assessment_results', 'assessment_assignments', 'assessment_paper_versions', 'assessment_papers', 'assessment_questions'):
        op.drop_table(name)
