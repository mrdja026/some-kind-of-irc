from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from src.core.database import Base, engine
from src.api.endpoints.auth import router as auth_router
from src.api.endpoints.channels import router as channels_router
from src.api.endpoints.media import router as media_router
from src.services.websocket_manager import manager
from src.services.irc_logger import log_privmsg
from src.models import User, Channel, Message, Membership
from contextlib import asynccontextmanager

# Lifespan event handler
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create database tables
    Base.metadata.create_all(bind=engine)

    # Ensure new columns exist for existing databases
    with engine.connect() as connection:
        result = connection.execute(text("PRAGMA table_info(messages)"))
        columns = {row[1] for row in result}
        if columns and "image_url" not in columns:
            connection.execute(text("ALTER TABLE messages ADD COLUMN image_url TEXT"))
            connection.commit()
    
    # Create default channels on startup
    from src.core.database import SessionLocal
    db = SessionLocal()
    default_channels = ["#general", "#random"]
    for channel_name in default_channels:
        db_channel = db.query(Channel).filter(Channel.name == channel_name).first()
        if not db_channel:
            new_channel = Channel(name=channel_name, type="public")
            db.add(new_channel)
    db.commit()
    db.close()
    
    yield

# Initialize FastAPI app
app = FastAPI(title="IRC Chat API", version="1.0.0", lifespan=lifespan)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth_router)
app.include_router(channels_router)
app.include_router(media_router)

# Health check endpoint
@app.get("/health")
async def health_check():
    return {"message": "server is running"}

# WebSocket endpoint
@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: int):
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
    except WebSocketDisconnect:
        manager.disconnect(client_id)

if __name__ == "__main__":
    import uvicorn
    import argparse
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8002)
    args = parser.parse_args()
    
    uvicorn.run(app, host="0.0.0.0", port=args.port)
