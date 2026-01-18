from fastapi.websockets import WebSocket
from typing import Dict, Set
from src.core.database import get_db
from src.models.membership import Membership

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[int, WebSocket] = {}
        self.client_channels: Dict[int, Set[int]] = {}  # client_id -> set of channel_ids

    async def connect(self, client_id: int, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[client_id] = websocket
        self.client_channels[client_id] = set()
        # Load existing channel memberships for the client
        db = next(get_db())
        memberships = db.query(Membership).filter(Membership.user_id == client_id).all()
        for membership in memberships:
            self.client_channels[client_id].add(int(membership.channel_id))
        db.close()

    def disconnect(self, client_id: int):
        if client_id in self.active_connections:
            del self.active_connections[client_id]
        if client_id in self.client_channels:
            del self.client_channels[client_id]

    async def send_personal_message(self, message: dict, client_id: int):
        if client_id in self.active_connections:
            await self.active_connections[client_id].send_json(message)

    async def broadcast(self, message: dict, channel_id: int):
        for client_id, connection in self.active_connections.items():
            if client_id in self.client_channels and channel_id in self.client_channels[client_id]:
                await connection.send_json(message)

    def add_client_to_channel(self, client_id: int, channel_id: int):
        if client_id in self.client_channels:
            self.client_channels[client_id].add(channel_id)

    def remove_client_from_channel(self, client_id: int, channel_id: int):
        if client_id in self.client_channels and channel_id in self.client_channels[client_id]:
            self.client_channels[client_id].remove(channel_id)

manager = ConnectionManager()
