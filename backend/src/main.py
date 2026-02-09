import os
import logging
from urllib.parse import urlparse
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from src.core.database import Base, engine
from src.core.config import settings as app_settings
from src.api.endpoints.auth import router as auth_router
from src.api.endpoints.channels import router as channels_router
from src.api.endpoints.media import router as media_router
from src.api.endpoints.ai import router as ai_router
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
    "http://localhost:42069",
    "http://127.0.0.1:42069",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
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
app.include_router(ai_router)
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
            # Handle incoming WebSocket messages
            if data["type"] == "message":
                log_privmsg(client_id, data.get("channel_id"), data.get("content", ""))
                await manager.broadcast(data, data["channel_id"])
            elif data["type"] == "typing":
                # Add user_id to typing message
                data["user_id"] = client_id
                await manager.broadcast(data, data["channel_id"])
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
        manager.disconnect(client_id)

if __name__ == "__main__":
    import uvicorn
    import argparse
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8002)
    args = parser.parse_args()
    
    uvicorn.run(app, host="0.0.0.0", port=args.port)
