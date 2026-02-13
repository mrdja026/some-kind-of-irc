"""Contract tests for game command transport tokens."""

import json
from pathlib import Path

from src.services.game_service import GAME_COMMANDS


def test_game_command_schema_matches_service_tokens() -> None:
    """Ensure external command schema stays in sync with backend validation."""
    schema_path = Path(__file__).resolve().parents[2] / "external_schemas" / "commands.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    command_enum = (
        schema["definitions"]["GameCommand"]["properties"]["payload"]["properties"]["command"]["enum"]
    )

    assert command_enum == GAME_COMMANDS
    assert all(" " not in token for token in command_enum)
