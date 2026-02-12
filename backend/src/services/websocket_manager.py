from fastapi.websockets import WebSocket
from typing import Dict, List, Set, Optional, Any, cast
from datetime import datetime
from src.core.database import get_db
from src.models.membership import Membership
from src.models.user import User
from src.services.irc_logger import state_store

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
        user = db.query(User).filter(User.id == client_id).first()
        if user:
            state_store.set_nick(client_id, cast(str, user.username))  # type: ignore[arg-type]
        memberships = db.query(Membership).filter(Membership.user_id == client_id).all()
        for membership in memberships:
            self.client_channels[client_id].add(cast(int, membership.channel_id))  # type: ignore[arg-type]
        db.close()

    def disconnect(self, client_id: int, websocket: Optional[WebSocket] = None):
        active = self.active_connections.get(client_id)
        if websocket is not None and active is not websocket:
            return
        if client_id in self.active_connections:
            del self.active_connections[client_id]
        if client_id in self.client_channels:
            del self.client_channels[client_id]

    async def send_personal_message(self, message: dict, client_id: int | Any):
        if client_id in self.active_connections:
            await self.active_connections[client_id].send_json(message)

    async def broadcast(self, message: dict, channel_id: int | Any):
        for client_id, connection in self.active_connections.items():
            if client_id in self.client_channels and channel_id in self.client_channels[client_id]:
                await connection.send_json(message)

    async def broadcast_game_state(self, snapshot: dict, channel_id: int | Any):
        """Broadcast game state update to all members of a game channel."""
        message = dict(snapshot)
        message["channel_id"] = int(channel_id)
        if "timestamp" in message:
            message["timestamp"] = datetime.utcnow().isoformat()
        await self.broadcast(message, channel_id)

    async def send_game_state_to_client(
        self,
        snapshot: dict,
        channel_id: int | Any,
        client_id: int | Any,
    ) -> None:
        """Send a full game state snapshot to a single client."""
        message = dict(snapshot)
        message["channel_id"] = int(channel_id)
        if "timestamp" in message:
            message["timestamp"] = datetime.utcnow().isoformat()
        await self.send_personal_message(message, client_id)

    async def broadcast_game_action(
        self,
        action_result: dict,
        channel_id: int | Any,
        executor_id: int | Any,
        snapshot: Optional[dict] = None,
    ):
        """Send action result to executor and push state update to channel."""
        message = {
            "type": "action_result",
            "channel_id": int(channel_id),
            "timestamp": datetime.utcnow().isoformat(),
            "payload": {
                "success": action_result.get("success", False),
                "action_type": action_result.get("command", "unknown"),
                "executor_id": executor_id,
                "target_id": action_result.get("target_id"),
                "message": action_result.get("message", ""),
                "error": {"code": "game_error", "message": action_result.get("error")} if action_result.get("error") else None
            }
        }
        await self.send_personal_message(message, executor_id)
        
        # If there's a snapshot/update, broadcast that too
        if snapshot:
            update_message = dict(snapshot)
            update_message["channel_id"] = int(channel_id)
            if "timestamp" in update_message:
                update_message["timestamp"] = datetime.utcnow().isoformat()
            await self.broadcast(update_message, channel_id)

    def add_client_to_channel(self, client_id: int | Any, channel_id: int | Any):
        if client_id in self.client_channels:
            self.client_channels[client_id].add(channel_id)

    def remove_client_from_channel(self, client_id: int | Any, channel_id: int | Any):
        if client_id in self.client_channels and channel_id in self.client_channels[client_id]:
            self.client_channels[client_id].remove(channel_id)

    # Data Processor WebSocket Events
    
    async def broadcast_document_uploaded(
        self,
        channel_id: int,
        document_id: str,
        uploaded_by: str,
        filename: str,
        thumbnail_url: Optional[str] = None
    ):
        """
        Broadcast document_uploaded event to all channel members.
        
        Notifies connected clients when a new document has been uploaded
        to a data-processor channel.
        """
        message = {
            "type": "document_uploaded",
            "document_id": document_id,
            "channel_id": channel_id,
            "uploaded_by": uploaded_by,
            "filename": filename,
            "thumbnail_url": thumbnail_url
        }
        await self.broadcast(message, channel_id)

    async def broadcast_ocr_progress(
        self,
        channel_id: int,
        document_id: str,
        stage: str,
        progress: int,
        message: str
    ):
        """
        Broadcast ocr_progress event to all channel members.
        
        Provides real-time updates on OCR processing stages:
        - preprocessing: Image preprocessing (noise reduction, deskew)
        - detection: Detecting text regions and document elements
        - extraction: Extracting text via Tesseract OCR
        - mapping: Mapping extracted text to annotations
        
        Args:
            channel_id: The channel ID
            document_id: The document being processed
            stage: One of "preprocessing", "detection", "extraction", "mapping"
            progress: Progress percentage (0-100)
            message: Human-readable progress message
        """
        event = {
            "type": "ocr_progress",
            "document_id": document_id,
            "channel_id": channel_id,
            "stage": stage,
            "progress": progress,
            "message": message
        }
        await self.broadcast(event, channel_id)

    async def broadcast_ocr_complete(
        self,
        channel_id: int,
        document_id: str,
        detected_regions: List[Dict[str, Any]],
        extracted_text: str
    ):
        """
        Broadcast ocr_complete event when document OCR processing finishes.
        
        Args:
            channel_id: The channel ID
            document_id: The document that was processed
            detected_regions: List of detected regions with bounding boxes, e.g.:
                [{
                    "id": "region-uuid",
                    "type": "text_block",
                    "x": 10, "y": 20, "width": 200, "height": 50,
                    "text": "extracted text",
                    "confidence": 0.95
                }]
            extracted_text: Full extracted text from the document
        """
        event = {
            "type": "ocr_complete",
            "document_id": document_id,
            "channel_id": channel_id,
            "detected_regions": detected_regions,
            "extracted_text": extracted_text
        }
        await self.broadcast(event, channel_id)

    async def broadcast_template_applied(
        self,
        channel_id: int,
        document_id: str,
        template_id: str,
        matched_regions: List[Dict[str, Any]],
        confidence: float
    ):
        """
        Broadcast template_applied event when a template is matched to a document.
        
        Args:
            channel_id: The channel ID
            document_id: The document the template was applied to
            template_id: The template that was applied
            matched_regions: List of matched template regions with transformed positions, e.g.:
                [{
                    "label_id": "label-uuid",
                    "label_name": "Invoice Number",
                    "label_type": "header",
                    "x": 100, "y": 50, "width": 200, "height": 30,
                    "matched_text": "INV-2026-001",
                    "confidence": 0.92
                }]
            confidence: Overall template match confidence (0.0-1.0)
        """
        event = {
            "type": "template_applied",
            "document_id": document_id,
            "channel_id": channel_id,
            "template_id": template_id,
            "matched_regions": matched_regions,
            "confidence": confidence
        }
        await self.broadcast(event, channel_id)

manager = ConnectionManager()
