"""create campus table

Revision ID: 888416120601
Revises: ac9f06ae07e1
Create Date: 2025-05-25 19:27:39.498999

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '888416120601'
down_revision: Union[str, None] = 'ac9f06ae07e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('campus',
                    sa.Column('code', sa.String(), nullable=False),
                    sa.PrimaryKeyConstraint('code')
                    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('campus')
