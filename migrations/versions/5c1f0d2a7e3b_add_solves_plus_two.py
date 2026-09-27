"""Add solves.plus_two

Revision ID: 5c1f0d2a7e3b
Revises: 08a2ce87419e
Create Date: 2026-09-27 10:05:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '5c1f0d2a7e3b'
down_revision = '08a2ce87419e'
branch_labels = None
depends_on = None


def upgrade():
    # Existing solves had no +2: the old rule made a late start a DNF.
    with op.batch_alter_table('solves', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('plus_two', sa.Boolean(), server_default=sa.false(), nullable=False)
        )


def downgrade():
    with op.batch_alter_table('solves', schema=None) as batch_op:
        batch_op.drop_column('plus_two')
