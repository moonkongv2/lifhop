"""add user ownership to entries

Revision ID: 9de9712adfec
Revises: 29f2d8fbdd99
Create Date: 2026-08-24 12:08:15.673485

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9de9712adfec'
down_revision: Union[str, Sequence[str], None] = '29f2d8fbdd99'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.add_column(
        "entries",
        sa.Column("user_id", sa.Integer(), nullable=True),
    )

    op.create_foreign_key(
        "fk_entries_user_id_users",
        "entries",
        "users",
        ["user_id"],
        ["id"],
    )

    op.alter_column(
        "entries",
        "user_id",
        nullable=False,
    )

def downgrade() -> None:
    op.drop_constraint(
        "fk_entries_user_id_users",
        "entries",
        type_="foreignkey",
    )

    op.drop_column(
        "entries",
        "user_id",
    )

