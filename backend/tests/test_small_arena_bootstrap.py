"""Focused tests for small-arena bootstrap, role policy, and turns."""

from __future__ import annotations

import secrets
import time
from typing import Generator, cast

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.core.database import Base
from src.models.channel import Channel
from src.models.game_state import GameState
from src.models.user import User
from src.services.battlefield_service import BattlefieldService
from src.services.game_service import GameService
from src.services.websocket_manager import manager as ws_manager


NPC_SEED_COUNT = 2


@pytest.fixture(autouse=True)
def _reset_singletons() -> Generator[None, None, None]:
    GameService._channel_turn_user.clear()
    GameService._channel_turn_order.clear()
    GameService._channel_priority_turns.clear()
    GameService._channel_priority_resume_from.clear()
    GameService._channel_status_history.clear()
    GameService._channel_human_user.clear()
    GameService._channel_forced_npc_users.clear()
    BattlefieldService._channel_cache.clear()
    ws_manager._client_last_pong.clear()
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


def _create_user(db_session, username: str) -> User:
    user = User(username=username, password_hash="dummy_hash", hash_type="bcrypt")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _user_id(user: User) -> int:
    return int(cast(int, user.id))


def _create_game_channel(db_session) -> Channel:
    channel = Channel(name="#game", type="public")
    db_session.add(channel)
    db_session.commit()
    db_session.refresh(channel)
    return channel


def _channel_id(channel: Channel) -> int:
    return int(cast(int, channel.id))


def _seed_npcs_to_baseline(db_session, game_service: GameService, channel_id: int) -> None:
    states = game_service.get_all_game_states_in_channel(channel_id)
    npc_count = sum(1 for state in states if bool(state.get("is_npc", False)))
    to_create = max(0, NPC_SEED_COUNT - npc_count)
    for _ in range(to_create):
        username = f"npc_{secrets.token_hex(4)}"
        npc_user = _create_user(db_session, username)
        game_service.bootstrap_small_arena_join(_user_id(npc_user), channel_id)


def test_first_join_bootstraps_exactly_one_human_and_two_npcs(db_session) -> None:
    game_service = GameService(db_session)
    channel = _create_game_channel(db_session)
    human = _create_user(db_session, "human_1")
    channel_id = _channel_id(channel)
    human_id = _user_id(human)

    game_service.bootstrap_small_arena_join(human_id, channel_id)
    _seed_npcs_to_baseline(db_session, game_service, channel_id)

    states = game_service.get_all_game_states_in_channel(channel_id)
    assert len(states) == 3

    human_states = [state for state in states if not bool(state.get("is_npc", False))]
    npc_states = [state for state in states if bool(state.get("is_npc", False))]

    assert len(human_states) == 1
    assert len(npc_states) == 2
    assert int(human_states[0]["user_id"]) == human_id

    snapshot_map = game_service.get_game_snapshot(channel_id)["payload"]["map"]
    assert snapshot_map["board_type"] == "staggered_hex"
    assert snapshot_map["layout"] == "odd_r"
    assert snapshot_map["width"] == 10
    assert snapshot_map["height"] == 10
    assert snapshot_map["grid_max_index"] == 9


def test_later_joiner_is_forced_to_npc_role(db_session) -> None:
    game_service = GameService(db_session)
    channel = _create_game_channel(db_session)
    first_human = _create_user(db_session, "human_1")
    later_joiner = _create_user(db_session, "human_2")
    channel_id = _channel_id(channel)

    game_service.bootstrap_small_arena_join(_user_id(first_human), channel_id)
    _seed_npcs_to_baseline(db_session, game_service, channel_id)

    game_service.bootstrap_small_arena_join(_user_id(later_joiner), channel_id)

    states = game_service.get_all_game_states_in_channel(channel_id)
    later_state = next(state for state in states if int(state["user_id"]) == _user_id(later_joiner))
    assert bool(later_state.get("is_npc", False)) is True


def test_human_slot_reassigned_after_human_leaves(db_session) -> None:
    game_service = GameService(db_session)
    channel = _create_game_channel(db_session)
    first_human = _create_user(db_session, "human_1")
    next_joiner = _create_user(db_session, "human_2")
    channel_id = _channel_id(channel)

    game_service.bootstrap_small_arena_join(_user_id(first_human), channel_id)
    _seed_npcs_to_baseline(db_session, game_service, channel_id)

    game_service.deactivate_session(_user_id(first_human), channel_id)
    game_service.bootstrap_small_arena_join(_user_id(next_joiner), channel_id)

    states = game_service.get_all_game_states_in_channel(channel_id)
    next_state = next(state for state in states if int(state["user_id"]) == _user_id(next_joiner))
    assert bool(next_state.get("is_npc", False)) is False


def test_spawn_positions_avoid_blocked_obstacles(db_session) -> None:
    game_service = GameService(db_session)
    channel = _create_game_channel(db_session)
    channel_id = _channel_id(channel)

    first_human = _create_user(db_session, "human_1")
    game_service.bootstrap_small_arena_join(_user_id(first_human), channel_id)
    _seed_npcs_to_baseline(db_session, game_service, channel_id)

    for index in range(4):
        joiner = _create_user(db_session, f"joiner_{index}")
        game_service.bootstrap_small_arena_join(_user_id(joiner), channel_id)

    obstacle_positions = game_service._get_obstacle_positions(channel_id)
    players = game_service.get_all_game_states_in_channel(channel_id)

    seen_positions = set()
    for player in players:
        position = player.get("position", {})
        pair = (int(position.get("x", -1)), int(position.get("y", -1)))
        assert pair not in obstacle_positions
        assert pair not in seen_positions
        seen_positions.add(pair)


def test_successful_action_advances_turn_and_keeps_update_turn_field(db_session) -> None:
    game_service = GameService(db_session)
    channel = _create_game_channel(db_session)
    first_human = _create_user(db_session, "human_1")
    channel_id = _channel_id(channel)

    game_service.bootstrap_small_arena_join(_user_id(first_human), channel_id)
    _seed_npcs_to_baseline(db_session, game_service, channel_id)

    for state in game_service.get_all_game_states_in_channel(channel_id):
        ws_manager._client_last_pong[int(state["user_id"])] = time.time()

    active_before = game_service.get_active_turn_user_id(channel_id)
    assert active_before is not None

    result = game_service.execute_command("heal", int(active_before), channel_id=channel_id)
    assert bool(result.get("success", False)) is True
    assert result.get("active_turn_user_id") is not None
    active_after = game_service.get_active_turn_user_id(channel_id)
    assert active_after is not None
    assert int(result["active_turn_user_id"]) == int(active_after)

    update = game_service.get_game_state_update(channel_id)
    assert "active_turn_user_id" in update["payload"]


def test_failed_npc_move_does_not_block_turn_loop(db_session, monkeypatch) -> None:
    game_service = GameService(db_session)
    channel = _create_game_channel(db_session)
    human = _create_user(db_session, "human_1")
    channel_id = _channel_id(channel)

    game_service.bootstrap_small_arena_join(_user_id(human), channel_id)
    _seed_npcs_to_baseline(db_session, game_service, channel_id)

    states = game_service.get_all_game_states_in_channel(channel_id)
    human_id = int(next(state["user_id"] for state in states if not bool(state.get("is_npc", False))))
    npc_ids = [int(state["user_id"]) for state in states if bool(state.get("is_npc", False))]
    assert len(npc_ids) == 2

    first_npc_state = db_session.query(GameState).filter(GameState.user_id == npc_ids[0]).first()
    second_npc_state = db_session.query(GameState).filter(GameState.user_id == npc_ids[1]).first()
    assert first_npc_state is not None
    assert second_npc_state is not None

    setattr(first_npc_state, "position_x", 0)
    setattr(first_npc_state, "position_y", 0)
    setattr(second_npc_state, "position_x", 5)
    setattr(second_npc_state, "position_y", 5)
    db_session.commit()

    def _scripted_npc_action(user_id: int, _: int):
        if user_id == npc_ids[0]:
            return ("move_n", None)
        if user_id == npc_ids[1]:
            return ("heal", None)
        return (None, None)

    monkeypatch.setattr(game_service, "_choose_npc_action", _scripted_npc_action)
    game_service._channel_turn_user[channel_id] = human_id
    for state in states:
        ws_manager._client_last_pong[int(state["user_id"])] = time.time()

    result = game_service.execute_command("heal", human_id, channel_id=channel_id)
    assert bool(result.get("success", False)) is True
    assert int(result.get("active_turn_user_id", 0)) == human_id

    npc_actions = result.get("npc_actions", [])
    assert any(int(action.get("executor_id", 0)) == npc_ids[1] for action in npc_actions if isinstance(action, dict))
