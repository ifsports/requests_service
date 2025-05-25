"""Update request table with team attribute

Revision ID: abefa3f7285b
Revises: 88a9b8076b18
Create Date: 2025-05-25 15:19:16.100583

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'abefa3f7285b'
down_revision: Union[str, None] = '88a9b8076b18'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('requests', sa.Column('team_id', sa.UUID(), nullable=False))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('requests', 'team_id')
