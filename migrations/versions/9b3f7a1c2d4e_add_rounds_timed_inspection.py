"""Add rounds.timed_inspection

Revision ID: 9b3f7a1c2d4e
Revises: 5c1f0d2a7e3b
Create Date: 2026-10-22 16:55:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9b3f7a1c2d4e'
down_revision = '5c1f0d2a7e3b'
branch_labels = None
depends_on = None


def upgrade():
    # Existing/in-flight rounds keep today's always-timed behaviour.
    with op.batch_alter_table('rounds', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('timed_inspection', sa.Boolean(), server_default=sa.true(), nullable=False)
        )


def downgrade():
    with op.batch_alter_table('rounds', schema=None) as batch_op:
        batch_op.drop_column('timed_inspection')
