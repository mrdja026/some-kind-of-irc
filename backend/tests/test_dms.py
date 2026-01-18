import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.core.database import Base
from src.main import app
from src.core.database import get_db
from src.models.user import User
from src.models.channel import Channel
from src.models.membership import Membership
from src.models.message import Message

# Setup in-memory SQLite database for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create all tables in the test database
Base.metadata.create_all(bind=engine)

# Override the get_db dependency to use the test database
def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

# Create a test client
client = TestClient(app)

# Test data - using shorter passwords to avoid bcrypt's 72-byte limit
TEST_USER1 = {"username": "testuser1", "password": "pass123"}
TEST_USER2 = {"username": "testuser2", "password": "pass123"}

@pytest.fixture
def test_users():
    # Clear existing users first
    with TestingSessionLocal() as db:
        db.query(User).delete()
        db.query(Channel).delete()
        db.query(Membership).delete()
        db.query(Message).delete()
        db.commit()
    
    # Create test users
    response1 = client.post("/auth/register", json=TEST_USER1)
    assert response1.status_code == 200
    
    response2 = client.post("/auth/register", json=TEST_USER2)
    assert response2.status_code == 200
    
    # Get user IDs from database
    with TestingSessionLocal() as db:
        user1 = db.query(User).filter(User.username == TEST_USER1["username"]).first()
        user2 = db.query(User).filter(User.username == TEST_USER2["username"]).first()
        assert user1 is not None
        assert user2 is not None
    
    return user1.id, user2.id

def test_create_dm_channel(test_users):
    """Test creating a direct message channel between two users."""
    user1_id, user2_id = test_users
    
    # Login as user1
    login_response = client.post("/auth/login", data={"username": TEST_USER1["username"], "password": TEST_USER1["password"]})
    assert login_response.status_code == 200
    
    # Create DM channel
    response = client.post(f"/channels/dm/{user2_id}")
    assert response.status_code == 200
    
    channel_data = response.json()
    assert channel_data["type"] == "private"
    assert "dm-" in channel_data["name"]
    
    # Verify both users are members
    with TestingSessionLocal() as db:
        memberships = db.query(Membership).filter(Membership.channel_id == channel_data["id"]).all()
        assert len(memberships) == 2
        
        user_ids = [m.user_id for m in memberships]
        assert user1_id in user_ids
        assert user2_id in user_ids

def test_get_dm_channels(test_users):
    """Test getting all direct messages for a user."""
    user1_id, user2_id = test_users
    
    # Login as user1
    login_response = client.post("/auth/login", data={"username": TEST_USER1["username"], "password": TEST_USER1["password"]})
    assert login_response.status_code == 200
    
    # Create DM channel
    dm_response = client.post(f"/channels/dm/{user2_id}")
    assert dm_response.status_code == 200
    dm_channel_id = dm_response.json()["id"]
    
    # Get all DM channels for user1
    response = client.get("/channels/dms")
    assert response.status_code == 200
    
    dms = response.json()
    assert len(dms) > 0
    
    # Verify the DM channel is in the list
    assert any(dm["id"] == dm_channel_id for dm in dms)

def test_send_and_receive_dm(test_users):
    """Test sending and receiving messages in a DM channel."""
    user1_id, user2_id = test_users
    
    # Login as user1
    login_response = client.post("/auth/login", data={"username": TEST_USER1["username"], "password": TEST_USER1["password"]})
    assert login_response.status_code == 200
    
    # Create DM channel
    dm_response = client.post(f"/channels/dm/{user2_id}")
    assert dm_response.status_code == 200
    channel_id = dm_response.json()["id"]
    
    # Send a message
    message_content = "Hello from test user 1!"
    message_response = client.post(f"/channels/{channel_id}/messages", json={"content": message_content})
    assert message_response.status_code == 200
    
    # Get messages
    messages_response = client.get(f"/channels/{channel_id}/messages")
    assert messages_response.status_code == 200
    
    messages = messages_response.json()
    assert len(messages) == 1
    assert messages[0]["content"] == message_content
    assert messages[0]["sender_id"] == user1_id

if __name__ == "__main__":
    pytest.main([__file__])
