"""Create request table

Revision ID: 88a9b8076b18
Revises: 
Create Date: 2025-05-25 13:15:52.523073

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '88a9b8076b18'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('requests',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('request_type', sa.Enum('approve_team', 'delete_team', 'remove_team_member', name='requesttypeenum'), nullable=False),
    sa.Column('reason', sa.String(), nullable=True),
    sa.Column('reason_rejected', sa.String(), nullable=True),
    sa.Column('status', sa.Enum('pendent', 'approved', 'rejected', name='requeststatusenum'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('requests')
