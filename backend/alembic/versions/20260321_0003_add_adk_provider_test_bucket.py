"""add adk_provider_test_bucket to users

Revision ID: 20260321_0003
Revises: 20260319_0002
Create Date: 2026-03-21

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20260321_0003"
down_revision: Union[str, None] = "20260319_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users", sa.Column("adk_provider_test_bucket", sa.String(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("users", "adk_provider_test_bucket")
