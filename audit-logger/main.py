"""Throwaway audit logger microservice for TD-5 testing."""
import asyncio
import logging
import sqlite3
from datetime import datetime
from fastapi import FastAPI, BackgroundTasks
from pydantic import BaseModel

app = FastAPI(title="Audit Logger (Throwaway)")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# In-memory SQLite for throwaway testing
DB_PATH = "/tmp/audit.db"


class AuditLog(BaseModel):
    timestamp: str
    username: str
    endpoint: str
    action: str
    allowed: bool


def init_db():
    """Initialize SQLite DB."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            username TEXT,
            endpoint TEXT,
            action TEXT,
            allowed BOOLEAN
        )
    """)
    conn.commit()
    conn.close()


@app.on_event("startup")
async def startup():
    init_db()
    logger.info("Audit logger started")


async def log_to_db(log: AuditLog):
    """Fire-and-forget logging to SQLite."""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute(
            """INSERT INTO audit_logs 
               (timestamp, username, endpoint, action, allowed) 
               VALUES (?, ?, ?, ?, ?)""",
            (log.timestamp, log.username, log.endpoint, log.action, log.allowed)
        )
        conn.commit()
        conn.close()
        logger.info(f"Audit logged: {log.username} - {log.action} - allowed={log.allowed}")
    except Exception as e:
        # Fire-and-forget: log error but don't fail
        logger.error(f"Audit log failed: {e}")


@app.post("/log")
async def create_log(log: AuditLog, background_tasks: BackgroundTasks):
    """Receive audit log entry."""
    background_tasks.add_task(log_to_db, log)
    return {"status": "queued"}


@app.get("/logs")
async def get_logs():
    """View all logs (for testing)."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute(
        "SELECT * FROM audit_logs ORDER BY timestamp DESC LIMIT 100"
    )
    rows = cursor.fetchall()
    conn.close()
    
    logs = [
        {
            "id": row[0],
            "timestamp": row[1],
            "username": row[2],
            "endpoint": row[3],
            "action": row[4],
            "allowed": bool(row[5])
        }
        for row in rows
    ]
    return {"logs": logs}


@app.get("/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8004)
