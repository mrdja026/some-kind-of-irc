import os
import logging
from datetime import datetime
from urllib.parse import urlparse
from typing import cast
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from src.core.database import Base, engine, get_db
from src.core.config import settings as app_settings
from src.api.endpoints.auth import router as auth_router, _ensure_npc_sessions
from src.api.endpoints.channels import router as channels_router
from src.api.endpoints.media import router as media_router
from src.api.endpoints.game import router as game_router
from src.api.endpoints.data_processor import router as data_processor_router
from src.services.websocket_manager import manager
from src.services.irc_logger import log_privmsg
from src.services.game_service import GameService
from src.services.event_subscriber import start_event_subscriber, stop_event_subscriber
from src.models import User, Channel, Message, Membership, GameState, GameSession
from contextlib import asynccontextmanager

logger = logging.getLogger("uvicorn.error")

# Lifespan event handler
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create database tables
    Base.metadata.create_all(bind=engine)

    # Ensure new columns exist for existing databases
    with engine.connect() as connection:
        # Check messages table
        result = connection.execute(text("PRAGMA table_info(messages)"))
        columns = {row[1] for row in result}
        if columns and "image_url" not in columns:
            connection.execute(text("ALTER TABLE messages ADD COLUMN image_url TEXT"))
            connection.commit()
        if columns and "target_user_id" not in columns:
            connection.execute(text("ALTER TABLE messages ADD COLUMN target_user_id INTEGER"))
            connection.commit()
        
        # Check users table
        result = connection.execute(text("PRAGMA table_info(users)"))
        user_columns = {row[1] for row in result}
        if user_columns and "profile_picture_url" not in user_columns:
            connection.execute(text("ALTER TABLE users ADD COLUMN profile_picture_url TEXT"))
            connection.commit()
        if user_columns and "display_name" not in user_columns:
            connection.execute(text("ALTER TABLE users ADD COLUMN display_name TEXT"))
            connection.execute(text("UPDATE users SET display_name = username WHERE display_name IS NULL"))
            connection.commit()
        if user_columns and "display_name_updated_at" not in user_columns:
            connection.execute(text("ALTER TABLE users ADD COLUMN display_name_updated_at DATETIME"))
            connection.commit()
        if user_columns and "updated_at" not in user_columns:
            # SQLite doesn't allow non-constant defaults in ALTER TABLE
            connection.execute(text("ALTER TABLE users ADD COLUMN updated_at DATETIME"))
            connection.execute(text("UPDATE users SET updated_at = CURRENT_TIMESTAMP WHERE updated_at IS NULL"))
            connection.commit()
    
        # Check channels table for is_data_processor column
        result = connection.execute(text("PRAGMA table_info(channels)"))
        channel_columns = {row[1] for row in result}
        if channel_columns and "is_data_processor" not in channel_columns:
            connection.execute(text("ALTER TABLE channels ADD COLUMN is_data_processor BOOLEAN DEFAULT 0"))
            connection.commit()
    
    # Create default channels on startup
    from src.core.database import SessionLocal
    from src.core.config import settings
    db = SessionLocal()
    default_channels = ["#general", "#random", "#ai", "#game"]
    
    # Add data-processor channel if feature is enabled
    if settings.data_processor_enabled:
        default_channels.append("#data-processor")
    
    for channel_name in default_channels:
        db_channel = db.query(Channel).filter(Channel.name == channel_name).first()
        if not db_channel:
            is_data_processor = (channel_name == "#data-processor")
            new_channel = Channel(name=channel_name, type="public", is_data_processor=is_data_processor)
            db.add(new_channel)
    db.commit()

    # Reset #game memberships and sessions, keep guest2 only
    game_channel = db.query(Channel).filter(Channel.name == "#game").first()
    if game_channel:
        channel_id = game_channel.id
        sessions = db.query(GameSession).filter(GameSession.channel_id == channel_id).all()
        game_state_ids = [session.game_state_id for session in sessions if session.game_state_id is not None]
        for session in sessions:
            db.delete(session)
        if game_state_ids:
            db.query(GameState).filter(GameState.id.in_(game_state_ids)).delete(synchronize_session=False)
        db.query(Membership).filter(Membership.channel_id == channel_id).delete(synchronize_session=False)

        guest_users = db.query(User).filter(
            User.username.like("guest_%"),
            User.username != "guest2",
        ).all()
        npc_users = db.query(User).filter(User.username.like("npc_%")).all()
        for user in guest_users + npc_users:
            db.query(Membership).filter(Membership.user_id == user.id).delete(synchronize_session=False)
            db.query(GameSession).filter(GameSession.user_id == user.id).delete(synchronize_session=False)
            db.query(GameState).filter(GameState.user_id == user.id).delete(synchronize_session=False)
            db.delete(user)
        db.commit()
    db.close()
    
    # Start Redis event subscriber for auto-join functionality
    start_event_subscriber()
    
    yield
    
    # Shutdown: stop event subscriber
    stop_event_subscriber()

# Initialize FastAPI app
app = FastAPI(title="IRC Chat API", version="1.0.0", lifespan=lifespan)

# CORS middleware
def _origin_from_url(value: str) -> str | None:
    parsed = urlparse(value)
    if not parsed.scheme or not parsed.hostname:
        return None
    if parsed.port:
        return f"{parsed.scheme}://{parsed.hostname}:{parsed.port}"
    return f"{parsed.scheme}://{parsed.hostname}"


_default_origins = [
    "http://localhost",
    "http://localhost:80",
    "http://127.0.0.1",
    "http://localhost:4269",
    "http://127.0.0.1:4269",
    "http://localhost:8080",
    "http://127.0.0.1:8080",
]
_extra_origins: list[str] = []
extra = os.getenv("ALLOWED_ORIGINS")
if extra:
    _extra_origins.extend([o.strip() for o in extra.split(",") if o.strip()])

for env_var in ("PUBLIC_BASE_URL", "VITE_PUBLIC_API_URL"):
    value = os.getenv(env_var)
    if value:
        origin = _origin_from_url(value.strip())
        if origin:
            _extra_origins.append(origin)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_default_origins + _extra_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth_router)
app.include_router(channels_router)
app.include_router(media_router)
app.include_router(game_router)
app.include_router(data_processor_router)

# Temporary root endpoint (backend should not serve frontend)
@app.get("/")
async def root():
    return {
        "message": "backend placeholder; frontend should serve /",
        "links": {"health": "/health", "docs": "/docs"},
    }

# Health check endpoint
@app.get("/health")
async def health_check():
    return {"message": "server is running"}

# WebSocket endpoint
@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: int):
    client_host = websocket.client.host if websocket.client else "unknown"
    logger.info("WebSocket connect client_id=%s host=%s", client_id, client_host)

    await manager.connect(client_id, websocket)
    try:
        while True:
            data = await websocket.receive_json()
            message_type = data.get("type")
            # Handle incoming WebSocket messages
            if message_type == "message":
                log_privmsg(client_id, data.get("channel_id"), data.get("content", ""))
                await manager.broadcast(data, data["channel_id"])
            elif message_type == "typing":
                # Add user_id to typing message
                data["user_id"] = client_id
                await manager.broadcast(data, data["channel_id"])
            elif message_type == "game_join":
                channel_id = data.get("channel_id")
                if channel_id is None:
                    await manager.send_personal_message(
                        {
                            "type": "game_join_ack",
                            "channel_id": None,
                            "timestamp": datetime.utcnow().isoformat(),
                            "payload": {
                                "status_code": 400,
                                "ready": False,
                                "message": "game_join requires channel_id",
                            },
                        },
                        client_id,
                    )
                    continue
                try:
                    resolved_channel_id = int(channel_id)
                except (TypeError, ValueError):
                    await manager.send_personal_message(
                        {
                            "type": "game_join_ack",
                            "channel_id": None,
                            "timestamp": datetime.utcnow().isoformat(),
                            "payload": {
                                "status_code": 400,
                                "ready": False,
                                "message": "game_join channel_id must be an integer",
                            },
                        },
                        client_id,
                    )
                    continue

                joined_channels = manager.client_channels.get(client_id, set())
                if resolved_channel_id not in joined_channels:
                    await manager.send_personal_message(
                        {
                            "type": "game_join_ack",
                            "channel_id": resolved_channel_id,
                            "timestamp": datetime.utcnow().isoformat(),
                            "payload": {
                                "status_code": 403,
                                "ready": False,
                                "message": "User is not a member of this channel",
                            },
                        },
                        client_id,
                    )
                    continue

                db = next(get_db())
                try:
                    channel = db.query(Channel).filter(Channel.id == resolved_channel_id).first()
                    if channel is None:
                        await manager.send_personal_message(
                            {
                                "type": "game_join_ack",
                                "channel_id": resolved_channel_id,
                                "timestamp": datetime.utcnow().isoformat(),
                                "payload": {
                                    "status_code": 404,
                                    "ready": False,
                                    "message": "Channel not found",
                                },
                            },
                            client_id,
                        )
                        continue

                    game_service = GameService(db)
                    if not game_service.is_game_channel(cast(str, channel.name)):
                        await manager.send_personal_message(
                            {
                                "type": "game_join_ack",
                                "channel_id": resolved_channel_id,
                                "timestamp": datetime.utcnow().isoformat(),
                                "payload": {
                                    "status_code": 400,
                                    "ready": False,
                                    "message": "Not a game channel",
                                },
                            },
                            client_id,
                        )
                        continue

                    # WS-first small arena initialization sequence:
                    # 1) Generate deterministic 10x10 staggered battlefield + obstacle clumps
                    # 2) Ensure joining participant session/state and role assignment
                    # 3) Seed baseline NPCs and normalize spawns with blocked-check + BFS
                    game_service.bootstrap_small_arena_join(client_id, resolved_channel_id)
                    _ensure_npc_sessions(db, game_service, resolved_channel_id)

                    snapshot = game_service.get_game_snapshot(resolved_channel_id)

                    await manager.send_personal_message(
                        {
                            "type": "game_join_ack",
                            "channel_id": resolved_channel_id,
                            "timestamp": datetime.utcnow().isoformat(),
                            "payload": {
                                "status_code": 200,
                                "ready": True,
                                "message": "game ready",
                            },
                        },
                        client_id,
                    )
                    await manager.send_game_state_to_client(snapshot, resolved_channel_id, client_id)

                    update = game_service.get_game_state_update(resolved_channel_id)
                    await manager.broadcast_game_state(update, resolved_channel_id)
                finally:
                    db.close()
            elif message_type == "game_command":
                channel_id = data.get("channel_id")
                if channel_id is None:
                    await manager.send_personal_message(
                        {
                            "type": "error",
                            "channel_id": None,
                            "timestamp": datetime.utcnow().isoformat(),
                            "payload": {
                                "code": "missing_channel_id",
                                "message": "game_command requires channel_id",
                                "details": {},
                            },
                        },
                        client_id,
                    )
                    continue

                try:
                    resolved_channel_id = int(channel_id)
                except (TypeError, ValueError):
                    await manager.send_personal_message(
                        {
                            "type": "error",
                            "channel_id": None,
                            "timestamp": datetime.utcnow().isoformat(),
                            "payload": {
                                "code": "invalid_channel_id",
                                "message": "game_command channel_id must be an integer",
                                "details": {"channel_id": channel_id},
                            },
                        },
                        client_id,
                    )
                    continue

                db = next(get_db())
                game_service = GameService(db)

                payload = data.get("payload", {})
                command = payload.get("command")
                target_username = payload.get("target_username")

                if command:
                    result = game_service.execute_command(
                        command=command,
                        executor_id=client_id,
                        target_username=target_username,
                        channel_id=resolved_channel_id,
                    )

                    await manager.broadcast_game_action(
                        action_result=result,
                        channel_id=resolved_channel_id,
                        executor_id=client_id,
                        snapshot=None,
                    )
                    if result.get("success"):
                        state_update = game_service.get_game_state_update(resolved_channel_id)
                        await manager.broadcast_game_state(state_update, resolved_channel_id)

                        if game_service.is_npc_turn(resolved_channel_id):
                            npc_steps = game_service.process_npc_turn_chain(resolved_channel_id)
                            for step in npc_steps:
                                if not isinstance(step, dict):
                                    continue
                                npc_action = step.get("action_result", {})
                                npc_update = step.get("state_update", {})
                                if not isinstance(npc_action, dict):
                                    continue
                                if not isinstance(npc_update, dict):
                                    continue
                                npc_executor_id = int(npc_action.get("executor_id", 0))
                                if npc_executor_id <= 0:
                                    continue
                                await manager.broadcast_game_action(
                                    action_result=npc_action,
                                    channel_id=resolved_channel_id,
                                    executor_id=npc_executor_id,
                                    snapshot=None,
                                    broadcast_failure_to_channel=True,
                                )
                                await manager.broadcast_game_state(npc_update, resolved_channel_id)
                else:
                    await manager.send_personal_message(
                        {
                            "type": "error",
                            "channel_id": resolved_channel_id,
                            "timestamp": datetime.utcnow().isoformat(),
                            "payload": {
                                "code": "missing_command",
                                "message": "game_command payload requires command",
                                "details": {},
                            },
                        },
                        client_id,
                    )
                db.close()
            elif message_type == "ping":
                # P6: Record client heartbeat for stale detection
                manager.record_client_pong(client_id)
                ping_payload = data.get("payload", {})
                sent_at_ms = None
                if isinstance(ping_payload, dict):
                    sent_at_ms = ping_payload.get("sent_at_ms")
                await manager.send_personal_message(
                    {
                        "type": "pong",
                        "timestamp": datetime.utcnow().isoformat(),
                        "payload": {
                            "sent_at_ms": sent_at_ms,
                        },
                    },
                    client_id,
                )

    except WebSocketDisconnect as exc:
        logger.info(
            "WebSocket disconnect client_id=%s host=%s code=%s",
            client_id,
            client_host,
            exc.code,
        )
    except Exception:
        logger.exception("WebSocket error client_id=%s host=%s", client_id, client_host)
    finally:
        manager.disconnect(client_id, websocket)


if __name__ == "__main__":
    import uvicorn
    import argparse
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8002)
    args = parser.parse_args()
    
    uvicorn.run(app, host="0.0.0.0", port=args.port)
