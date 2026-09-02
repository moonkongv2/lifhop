"""link import jobs to artifacts

Revision ID: 7d1a55df4aca
Revises: dcd0ad3a8da0
Create Date: 2026-09-02 13:25:09.971193

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7d1a55df4aca'
down_revision: Union[str, Sequence[str], None] = 'dcd0ad3a8da0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'import_jobs',
        sa.Column(
            'artifact_id',
            sa.Integer(),
            nullable=False,
        ),
    )

    op.create_foreign_key(
        'fk_import_jobs_artifact_id',
        'import_jobs',
        'import_artifacts',
        ['artifact_id'],
        ['id'],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        'fk_import_jobs_artifact_id',
        'import_jobs',
        type_='foreignkey',
    )

    op.drop_column(
        'import_jobs',
        'artifact_id',
    )
