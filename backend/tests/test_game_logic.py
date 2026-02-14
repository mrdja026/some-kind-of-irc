"""Unit tests for current game service behavior."""

from __future__ import annotations

from typing import Any, Dict, Generator, List, Tuple, cast

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.core.database import Base
from src.models.channel import Channel
from src.models.game_session import GameSession
from src.models.game_state import GameState
from src.models.user import User
from src.services.battlefield_service import BattlefieldService, GRID_SIZE
from src.services.game_service import ATTACK_DAMAGE, HEAL_AMOUNT, GameService


@pytest.fixture(autouse=True)
def _reset_singletons() -> Generator[None, None, None]:
    GameService._channel_turn_user.clear()
    GameService._channel_turn_order.clear()
    GameService._channel_priority_turns.clear()
    GameService._channel_priority_resume_from.clear()
    GameService._channel_status_history.clear()
    GameService._channel_human_user.clear()
    GameService._channel_forced_npc_users.clear()
    GameService._channel_turn_budget.clear()
    GameService._channel_turn_context_cache.clear()
    BattlefieldService._channel_cache.clear()
    yield


@pytest.fixture(scope="function")
def db_session() -> Generator[Session, None, None]:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def game_service(db_session):
    return GameService(db_session)


def _create_user(db_session, username: str) -> User:
    user = User(username=username, password_hash="dummy_hash", hash_type="bcrypt")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _create_state(db_session, user_id: int, position: Tuple[int, int], health: int = 100, max_health: int = 100) -> GameState:
    state = GameState(
        user_id=user_id,
        position_x=position[0],
        position_y=position[1],
        health=health,
        max_health=max_health,
    )
    db_session.add(state)
    db_session.commit()
    db_session.refresh(state)
    return state


def _create_session(db_session, user_id: int, game_state_id: int, channel_id: int) -> GameSession:
    session = GameSession(
        user_id=user_id,
        game_state_id=game_state_id,
        channel_id=channel_id,
        is_active=True,
    )
    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)
    return session


@pytest.fixture
def test_user(db_session):
    return _create_user(db_session, "testuser")


@pytest.fixture
def test_user2(db_session):
    return _create_user(db_session, "testuser2")


@pytest.fixture
def test_channel(db_session):
    channel = Channel(name="#game", type="public")
    db_session.add(channel)
    db_session.commit()
    db_session.refresh(channel)
    return channel


class TestGameStateCreation:
    def test_create_game_state(self, game_service, test_user):
        game_state = game_service.get_or_create_game_state(test_user.id)

        assert game_state is not None
        assert game_state.user_id == test_user.id
        assert 0 <= game_state.position_x < GRID_SIZE
        assert 0 <= game_state.position_y < GRID_SIZE
        assert game_state.health == 100
        assert game_state.max_health == 100

    def test_get_existing_game_state(self, game_service, test_user):
        state1 = game_service.get_or_create_game_state(test_user.id)
        state2 = game_service.get_or_create_game_state(test_user.id)

        assert state1.id == state2.id
        assert state1.position_x == state2.position_x
        assert state1.position_y == state2.position_y


class TestMovement:
    @pytest.mark.parametrize(
        "command,expected",
        [
            ("move_n", (5, 4)),
            ("move_ne", (6, 4)),
            ("move_se", (6, 5)),
            ("move_s", (6, 6)),
            ("move_sw", (5, 6)),
            ("move_nw", (4, 5)),
        ],
    )
    def test_hex_direction_moves(self, game_service, test_user, db_session, command: str, expected: Tuple[int, int]):
        _create_state(db_session, test_user.id, (5, 5))

        result = game_service.execute_command(command, test_user.id)

        assert result["success"] is True
        assert result["game_state"]["position_x"] == expected[0]
        assert result["game_state"]["position_y"] == expected[1]

    @pytest.mark.parametrize(
        "legacy,new_cmd",
        [
            ("move_up", "move_n"),
            ("move_down", "move_s"),
            ("move_left", "move_sw"),
            ("move_right", "move_se"),
        ],
    )
    def test_legacy_move_aliases_execute(self, game_service, test_user, db_session, legacy: str, new_cmd: str):
        _create_state(db_session, test_user.id, (5, 5))

        legacy_result = game_service.execute_command(legacy, test_user.id)
        db_session.query(GameState).filter(GameState.user_id == test_user.id).delete()
        db_session.commit()
        _create_state(db_session, test_user.id, (5, 5))
        new_result = game_service.execute_command(new_cmd, test_user.id)

        assert legacy_result["success"] is True
        assert legacy_result["position"] == new_result["position"]

    def test_move_rejected_outside_play_zone(self, game_service, test_user, db_session):
        _create_state(db_session, test_user.id, (0, 0))

        result = game_service.execute_command("move_n", test_user.id)

        assert result["success"] is False
        assert "outside battle zone" in result["error"].lower()


class TestCombat:
    def test_attack_another_user(self, game_service, test_user, test_user2, db_session):
        _create_state(db_session, test_user.id, (5, 5), health=100)
        _create_state(db_session, test_user2.id, (6, 5), health=100)

        result = game_service.execute_command("attack", test_user.id, test_user2.username)

        assert result["success"] is True
        assert result["game_state"]["health"] == 100 - ATTACK_DAMAGE
        assert result["target_id"] == test_user2.id

    def test_attack_self_fails(self, game_service, test_user, db_session):
        _create_state(db_session, test_user.id, (5, 5), health=100)

        result = game_service.execute_command("attack", test_user.id)

        assert result["success"] is False
        assert "cannot attack yourself" in result["error"].lower()

    def test_attack_fails_when_target_out_of_range(self, game_service, test_user, test_user2, db_session):
        _create_state(db_session, test_user.id, (5, 5), health=100)
        _create_state(db_session, test_user2.id, (8, 5), health=100)

        result = game_service.execute_command("attack", test_user.id, test_user2.username)

        assert result["success"] is False
        assert "out of range" in str(result.get("error", "")).lower()

    def test_heal_is_capped_at_max_health(self, game_service, test_user, db_session):
        _create_state(db_session, test_user.id, (5, 5), health=95, max_health=100)

        result = game_service.execute_command("heal", test_user.id)

        assert result["success"] is True
        assert result["game_state"]["health"] == 100
        assert "healed for 5" in result["message"].lower()

    def test_heal_damaged_user(self, game_service, test_user, db_session):
        _create_state(db_session, test_user.id, (5, 5), health=50, max_health=100)

        result = game_service.execute_command("heal", test_user.id)

        assert result["success"] is True
        assert result["game_state"]["health"] == 50 + HEAL_AMOUNT


class TestCommandParsing:
    def test_parse_hex_move(self, game_service):
        assert game_service.parse_command("move ne") == ("move_ne", None)

    def test_parse_legacy_move_alias(self, game_service):
        assert game_service.parse_command("move up") == ("move_n", None)

    def test_parse_attack_with_mention(self, game_service):
        assert game_service.parse_command("attack @player2") == ("attack", "player2")

    def test_parse_invalid_command(self, game_service):
        assert game_service.parse_command("invalid command") is None


class TestSnapshotAndSpawns:
    def test_snapshot_exposes_small_arena_map_metadata(self, game_service, test_user, test_channel):
        game_service.bootstrap_small_arena_join(test_user.id, test_channel.id)
        snapshot = game_service.get_game_snapshot(test_channel.id)

        payload_map = snapshot["payload"]["map"]
        assert payload_map["board_type"] == "staggered_hex"
        assert payload_map["layout"] == "odd_r"
        assert payload_map["width"] == GRID_SIZE
        assert payload_map["height"] == GRID_SIZE
        assert payload_map["grid_max_index"] == GRID_SIZE - 1

    def test_spawns_avoid_obstacles(self, game_service, db_session, test_channel):
        users = [_create_user(db_session, f"player{i}") for i in range(5)]

        positions = []
        for user in users:
            game_service.get_or_create_game_session(user.id, test_channel.id)
            state = game_service.get_or_create_game_state(user.id, test_channel.id)
            positions.append((state.position_x, state.position_y))

        obstacle_positions = game_service._get_obstacle_positions(test_channel.id)
        for position in positions:
            assert position not in obstacle_positions

    def test_snapshot_normalizes_player_off_obstacle(self, game_service, db_session, test_user, test_channel):
        generated = BattlefieldService.get_or_create(test_channel.id)
        obstacle = generated["obstacles"][0]["position"]
        obstacle_xy = (int(obstacle["x"]), int(obstacle["y"]))

        bad_state = _create_state(db_session, test_user.id, obstacle_xy)
        session = GameSession(
            user_id=test_user.id,
            game_state_id=bad_state.id,
            channel_id=test_channel.id,
            is_active=True,
        )
        db_session.add(session)
        db_session.commit()

        snapshot = game_service.get_game_snapshot(test_channel.id)
        assert snapshot["type"] == "game_snapshot"

        db_session.refresh(bad_state)
        normalized = (
            int(cast(int, bad_state.position_x)),
            int(cast(int, bad_state.position_y)),
        )
        assert normalized not in game_service._get_obstacle_positions(test_channel.id)

    def test_turn_context_exposes_attackable_and_surroundings_diff(self, game_service, db_session, test_channel):
        user_1 = _create_user(db_session, "tc_player_1")
        user_2 = _create_user(db_session, "tc_player_2")
        user_1_id = int(cast(int, user_1.id))
        user_2_id = int(cast(int, user_2.id))

        state_1 = _create_state(db_session, user_1_id, (5, 5), health=100)
        state_2 = _create_state(db_session, user_2_id, (6, 5), health=100)
        _create_session(db_session, user_1_id, int(cast(int, state_1.id)), int(cast(int, test_channel.id)))
        _create_session(db_session, user_2_id, int(cast(int, state_2.id)), int(cast(int, test_channel.id)))

        game_service.set_active_turn_user(int(cast(int, test_channel.id)), user_1_id)

        first_update = game_service.get_game_state_update(int(cast(int, test_channel.id)))
        first_context = cast(Dict[str, Any], first_update["payload"]["turn_context"])

        assert int(first_context["actor_user_id"]) == user_1_id
        assert user_2_id in cast(List[int], first_context["attackable_target_ids"])
        assert any(
            str(cast(Dict[str, Any], item).get("entity_id", "")) == f"player:{user_2_id}"
            for item in cast(List[Any], first_context["surroundings"])
        )
        first_diff = cast(Dict[str, Any], first_context["surroundings_diff"])
        assert int(first_diff["revision"]) >= 1
        assert len(cast(List[Any], first_diff["added"])) >= 1

        setattr(state_2, "position_x", 9)
        setattr(state_2, "position_y", 9)
        db_session.commit()

        second_update = game_service.get_game_state_update(int(cast(int, test_channel.id)))
        second_context = cast(Dict[str, Any], second_update["payload"]["turn_context"])
        assert user_2_id not in cast(List[int], second_context["attackable_target_ids"])
        second_diff = cast(Dict[str, Any], second_context["surroundings_diff"])
        assert int(second_diff["revision"]) > int(first_diff["revision"])
        assert any(
            str(cast(Dict[str, Any], item).get("entity_id", "")) == f"player:{user_2_id}"
            for item in cast(List[Any], second_diff["removed"])
        )
