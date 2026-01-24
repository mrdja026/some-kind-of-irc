import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.core.database import Base
from src.main import app
from src.core.database import get_db
from src.models.user import User

# Setup in-memory SQLite database for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_display_name.db"

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

# Test data
TEST_USER1 = {"username": "testuser1", "password": "pass123"}
TEST_USER2 = {"username": "testuser2", "password": "pass123"}

@pytest.fixture
def test_users():
    # Clear existing users first
    with TestingSessionLocal() as db:
        db.query(User).delete()
        db.commit()

    # Create test users
    response1 = client.post("/auth/register", json=TEST_USER1)
    assert response1.status_code == 200

    response2 = client.post("/auth/register", json=TEST_USER2)
    assert response2.status_code == 200

    return TEST_USER1, TEST_USER2

def test_display_name_initially_null(test_users):
    """Test that display_name is initially null and defaults to username."""
    user1, user2 = test_users

    # Login as user1
    login_response = client.post("/auth/login", data={"username": user1["username"], "password": user1["password"]})
    assert login_response.status_code == 200

    # Get current user
    me_response = client.get("/auth/me")
    assert me_response.status_code == 200
    user_data = me_response.json()

    # Initially display_name should be null, but API should return username as fallback
    assert user_data["username"] == user1["username"]
    assert user_data["display_name"] is None

def test_update_display_name_success(test_users):
    """Test successfully updating display name."""
    user1, user2 = test_users

    # Login as user1
    login_response = client.post("/auth/login", data={"username": user1["username"], "password": user1["password"]})
    assert login_response.status_code == 200

    # Update display name
    new_display_name = "Test User One"
    update_response = client.put("/auth/me", json={"display_name": new_display_name})
    assert update_response.status_code == 200

    user_data = update_response.json()
    assert user_data["display_name"] == new_display_name
    assert user_data["username"] == user1["username"]  # username unchanged

def test_display_name_uniqueness(test_users):
    """Test that display names must be unique."""
    user1, user2 = test_users

    # Login as user1 and set display name
    login_response = client.post("/auth/login", data={"username": user1["username"], "password": user1["password"]})
    assert login_response.status_code == 200

    new_display_name = "Unique Name"
    update_response = client.put("/auth/me", json={"display_name": new_display_name})
    assert update_response.status_code == 200

    # Login as user2 and try to use the same display name
    login_response2 = client.post("/auth/login", data={"username": user2["username"], "password": user2["password"]})
    assert login_response2.status_code == 200

    update_response2 = client.put("/auth/me", json={"display_name": new_display_name})
    assert update_response2.status_code == 400
    assert "already taken" in update_response2.json()["detail"]

def test_display_name_validation(test_users):
    """Test display name validation rules."""
    user1, user2 = test_users

    # Login as user1
    login_response = client.post("/auth/login", data={"username": user1["username"], "password": user1["password"]})
    assert login_response.status_code == 200

    # Test empty display name
    update_response = client.put("/auth/me", json={"display_name": ""})
    assert update_response.status_code == 400
    assert "cannot be empty" in update_response.json()["detail"]

    # Test too long display name
    long_name = "a" * 51
    update_response = client.put("/auth/me", json={"display_name": long_name})
    assert update_response.status_code == 400
    assert "50 characters or less" in update_response.json()["detail"]

def test_display_name_fallback_to_username(test_users):
    """Test that when display_name is null, username is used as display name."""
    user1, user2 = test_users

    # Login as user1
    login_response = client.post("/auth/login", data={"username": user1["username"], "password": user1["password"]})
    assert login_response.status_code == 200

    # Get user data - should show username when display_name is null
    me_response = client.get("/auth/me")
    assert me_response.status_code == 200
    user_data = me_response.json()
    assert user_data["display_name"] is None
    assert user_data["username"] == user1["username"]

def test_search_users_by_display_name(test_users):
    """Test searching users by display name."""
    user1, user2 = test_users

    # Login as user1 and set display name
    login_response = client.post("/auth/login", data={"username": user1["username"], "password": user1["password"]})
    assert login_response.status_code == 200

    display_name = "Searchable User"
    update_response = client.put("/auth/me", json={"display_name": display_name})
    assert update_response.status_code == 200

    # Search for the display name
    search_response = client.get(f"/auth/users/search?username={display_name[:5]}")  # partial match
    assert search_response.status_code == 200
    results = search_response.json()
    assert len(results) > 0
    assert any(user["display_name"] == display_name for user in results)

def test_search_users_by_username_still_works(test_users):
    """Test that searching by username still works."""
    user1, user2 = test_users

    # Login as user1
    login_response = client.post("/auth/login", data={"username": user1["username"], "password": user1["password"]})
    assert login_response.status_code == 200

    # Search for username
    search_response = client.get(f"/auth/users/search?username={user1['username'][:5]}")
    assert search_response.status_code == 200
    results = search_response.json()
    assert len(results) > 0
    assert any(user["username"] == user1["username"] for user in results)

if __name__ == "__main__":
    pytest.main([__file__])