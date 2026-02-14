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


def test_game_command_schema_timestamp_is_integer() -> None:
    schema_path = Path(__file__).resolve().parents[2] / "external_schemas" / "commands.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    timestamp_type = (
        schema["definitions"]["GameCommand"]["properties"]["payload"]["properties"]["timestamp"]["type"]
    )
    assert timestamp_type == "integer"


def test_event_schema_requires_turn_context_and_map_fields() -> None:
    events_path = Path(__file__).resolve().parents[2] / "external_schemas" / "events.json"
    events = json.loads(events_path.read_text(encoding="utf-8"))

    snapshot_payload = events["definitions"]["GameSnapshot"]["properties"]["payload"]
    snapshot_required = snapshot_payload["required"]
    assert "turn_context" in snapshot_required
    assert "map" in snapshot_required

    map_required = snapshot_payload["properties"]["map"]["required"]
    assert map_required == ["board_type", "layout", "width", "height", "grid_max_index"]

    update_payload = events["definitions"]["GameStateUpdate"]["properties"]["payload"]
    update_required = update_payload["required"]
    assert "turn_context" in update_required


def test_game_types_turn_context_structure_is_present() -> None:
    types_path = Path(__file__).resolve().parents[2] / "external_schemas" / "game_types.json"
    game_types = json.loads(types_path.read_text(encoding="utf-8"))

    turn_context = game_types["definitions"]["TurnContext"]
    assert turn_context["required"] == [
        "actor_user_id",
        "attackable_target_ids",
        "surroundings",
        "surroundings_diff",
    ]

    diff_required = turn_context["properties"]["surroundings_diff"]["required"]
    assert diff_required == ["revision", "added", "removed", "changed"]
