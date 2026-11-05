"""Preserve cleared category confirmation and schedule index retries fairly."""
from alembic import op
import sqlalchemy as sa

revision = 'e973ff14b005'
down_revision = 'd862ee03b004'
branch_labels = None
depends_on = None


def upgrade():
    for name in ['attempt_count', 'failure_count', 'last_attempt_at', 'next_attempt_at']:
        op.add_column('index_events', sa.Column(name, sa.Integer(), nullable=False, server_default='0'))
    op.create_index('ix_index_events_due', 'index_events', ['state', 'next_attempt_at', 'last_attempt_at'])
    states = sa.table('talent_field_states', sa.column('talent_id'), sa.column('field'),
        sa.column('confirmed'), sa.column('source_type'), sa.column('source_version'))
    existing = states.alias('existing_category')
    # 旧人工表单提交已经确认全部类别；即使明细已清空，也可由标量确认记录恢复意图。
    for category in ['education', 'experience', 'project', 'skill', 'certificate']:
        source = sa.select(states.c.talent_id, sa.literal(category), sa.literal(True),
            sa.literal('manual'), sa.func.max(states.c.source_version)).where(
                states.c.field.in_(['name', 'phone', 'email']), states.c.confirmed.is_(True),
                states.c.source_type == 'manual', ~sa.exists(sa.select(existing.c.talent_id).where(
                    existing.c.talent_id == states.c.talent_id, existing.c.field == category))
            ).group_by(states.c.talent_id)
        op.execute(states.insert().from_select(
            ['talent_id', 'field', 'confirmed', 'source_type', 'source_version'], source))


def downgrade():
    # 确认元数据保留，避免回滚DDL时丢失人工清空意图；旧代码会忽略类别记录。
    op.drop_index('ix_index_events_due', 'index_events')
    for name in ['next_attempt_at', 'last_attempt_at', 'failure_count', 'attempt_count']:
        op.drop_column('index_events', name)
