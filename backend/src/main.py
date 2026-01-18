from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from src.core.database import Base, engine
from src.api.endpoints.auth import router as auth_router
from src.api.endpoints.channels import router as channels_router
from src.services.websocket_manager import manager
from src.models import User, Channel, Message, Membership
from contextlib import asynccontextmanager

# Lifespan event handler
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create database tables
    Base.metadata.create_all(bind=engine)
    
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
    allow_origins=["http://localhost:3000"],  # Specify frontend origin for security
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth_router)
app.include_router(channels_router)

# WebSocket endpoint
@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: int):
    await manager.connect(client_id, websocket)
    try:
        while True:
            data = await websocket.receive_json()
            # Handle incoming WebSocket messages
            if data["type"] == "message":
                await manager.broadcast(data, data["channel_id"])
            elif data["type"] == "typing":
                await manager.broadcast(data, data["channel_id"])
    except WebSocketDisconnect:
        manager.disconnect(client_id)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
