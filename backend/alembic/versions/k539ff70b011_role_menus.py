"""Optional role menu visibility; existing API grants remain authoritative."""
from alembic import op
import sqlalchemy as sa
revision='k539ff70b011'
down_revision='j428ee69a010'
branch_labels=None
depends_on=None

def upgrade():
    op.add_column('roles',sa.Column('enabled_menus',sa.JSON(),nullable=True))

def downgrade():
    op.drop_column('roles','enabled_menus')
