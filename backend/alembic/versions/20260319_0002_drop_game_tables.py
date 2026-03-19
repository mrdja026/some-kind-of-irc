"""drop game tables and #game channel

Revision ID: 20260319_0002
Revises: 20260226_0001
Create Date: 2026-03-19

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260319_0002"
down_revision: Union[str, None] = "20260226_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DROP TABLE IF EXISTS game_sessions")
    op.execute("DROP TABLE IF EXISTS game_states")
    op.execute(
        "DELETE FROM messages WHERE channel_id IN (SELECT id FROM channels WHERE name = '#game')"
    )
    op.execute(
        "DELETE FROM memberships WHERE channel_id IN (SELECT id FROM channels WHERE name = '#game')"
    )
    op.execute("DELETE FROM channels WHERE name = '#game'")


def downgrade() -> None:
    # Destructive upgrade: game data and #game channel are not restored.
    pass
