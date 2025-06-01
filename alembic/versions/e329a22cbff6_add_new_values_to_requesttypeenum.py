"""add_new_values_to_requesttypeenum

Revision ID: e329a22cbff6
Revises: 371cd73c3bae
Create Date: 2025-05-31 23:54:58.050750

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e329a22cbff6'
down_revision: Union[str, None] = '371cd73c3bae'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("ALTER TYPE requesttypeenum ADD VALUE 'add_team_member'")



def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DELETE FROM pg_enum WHERE enumlabel = 'add_team_member' AND enumtypid = (SELECT oid FROM pg_type WHERE typname = 'requesttypeenum')")
