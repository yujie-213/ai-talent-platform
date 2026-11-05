"""role grant optimistic version"""
from alembic import op
import sqlalchemy as sa
revision = '95ab21c732dd'
down_revision = '32d6da01954b'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('roles', sa.Column('version', sa.Integer(), nullable=False, server_default='1'))

def downgrade():
    op.drop_column('roles', 'version')
