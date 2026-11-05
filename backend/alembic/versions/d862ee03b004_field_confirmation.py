"""Explicit scalar confirmation including manually confirmed empty values."""
from alembic import op
import sqlalchemy as sa
revision = 'd862ee03b004'
down_revision = 'c751dd92b003'
branch_labels = None
depends_on = None


def upgrade():
    table = op.create_table('talent_field_states',
        sa.Column('talent_id', sa.String(36), sa.ForeignKey('talents.id'), primary_key=True),
        sa.Column('field', sa.String(20), primary_key=True),
        sa.Column('confirmed', sa.Boolean(), nullable=False), sa.Column('source_type', sa.String(20), nullable=False),
        sa.Column('source_version', sa.Integer(), nullable=False))
    talents = sa.table('talents', sa.column('id'), sa.column('version'))
    # 旧档案均为人工维护来源，不能因新功能默认为未确认而自动修改。
    for field in ['name', 'phone', 'email']:
        op.execute(table.insert().from_select(['talent_id', 'field', 'confirmed', 'source_type', 'source_version'],
            sa.select(talents.c.id, sa.literal(field), sa.literal(True), sa.literal('manual'), talents.c.version)))


def downgrade():
    op.drop_table('talent_field_states')
