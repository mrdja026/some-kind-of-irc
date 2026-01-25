"""
Unit tests for game logic
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.core.database import Base
from src.models.user import User
from src.models.game_state import GameState
from src.models.channel import Channel
from src.models.game_session import GameSession
from src.services.game_service import GameService, GRID_SIZE, ATTACK_DAMAGE, HEAL_AMOUNT


# Test database setup
@pytest.fixture(scope="function")
def db_session():
    """Create a test database session"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def game_service(db_session):
    """Create a GameService instance with test database"""
    return GameService(db_session)


@pytest.fixture
def test_user(db_session):
    """Create a test user"""
    user = User(
        username="testuser",
        email="test@example.com",
        password_hash="dummy_hash"
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def test_user2(db_session):
    """Create a second test user"""
    user = User(
        username="testuser2",
        email="test2@example.com",
        password_hash="dummy_hash"
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def test_channel(db_session):
    """Create a test game channel"""
    channel = Channel(
        name="#game",
        type="public"
    )
    db_session.add(channel)
    db_session.commit()
    db_session.refresh(channel)
    return channel


class TestGameStateCreation:
    """Test game state initialization"""
    
    def test_create_game_state(self, game_service, test_user):
        """Test creating a new game state"""
        game_state = game_service.get_or_create_game_state(test_user.id)
        
        assert game_state is not None
        assert game_state.user_id == test_user.id
        assert 0 <= game_state.position_x < GRID_SIZE
        assert 0 <= game_state.position_y < GRID_SIZE
        assert game_state.health == 100
        assert game_state.max_health == 100
    
    def test_get_existing_game_state(self, game_service, test_user):
        """Test retrieving existing game state"""
        game_state1 = game_service.get_or_create_game_state(test_user.id)
        original_pos_x = game_state1.position_x
        original_pos_y = game_state1.position_y
        
        game_state2 = game_service.get_or_create_game_state(test_user.id)
        
        assert game_state1.id == game_state2.id
        assert game_state2.position_x == original_pos_x
        assert game_state2.position_y == original_pos_y


class TestMovement:
    """Test movement commands"""
    
    def test_move_up(self, game_service, test_user, db_session):
        """Test moving up"""
        # Create game state with known position
        game_state = GameState(
            user_id=test_user.id,
            position_x=32,
            position_y=32,
            health=100,
            max_health=100
        )
        db_session.add(game_state)
        db_session.commit()
        
        result = game_service.execute_command("move up", test_user.id)
        
        assert result["success"] is True
        assert result["game_state"]["position_y"] == 31
        assert result["game_state"]["position_x"] == 32
        assert "up" in result["message"].lower()
    
    def test_move_down(self, game_service, test_user, db_session):
        """Test moving down"""
        game_state = GameState(
            user_id=test_user.id,
            position_x=32,
            position_y=32,
            health=100,
            max_health=100
        )
        db_session.add(game_state)
        db_session.commit()
        
        result = game_service.execute_command("move down", test_user.id)
        
        assert result["success"] is True
        assert result["game_state"]["position_y"] == 33
        assert result["game_state"]["position_x"] == 32
        assert "down" in result["message"].lower()
    
    def test_move_left(self, game_service, test_user, db_session):
        """Test moving left"""
        game_state = GameState(
            user_id=test_user.id,
            position_x=32,
            position_y=32,
            health=100,
            max_health=100
        )
        db_session.add(game_state)
        db_session.commit()
        
        result = game_service.execute_command("move left", test_user.id)
        
        assert result["success"] is True
        assert result["game_state"]["position_x"] == 31
        assert result["game_state"]["position_y"] == 32
        assert "left" in result["message"].lower()
    
    def test_move_right(self, game_service, test_user, db_session):
        """Test moving right"""
        game_state = GameState(
            user_id=test_user.id,
            position_x=32,
            position_y=32,
            health=100,
            max_health=100
        )
        db_session.add(game_state)
        db_session.commit()
        
        result = game_service.execute_command("move right", test_user.id)
        
        assert result["success"] is True
        assert result["game_state"]["position_x"] == 33
        assert result["game_state"]["position_y"] == 32
        assert "right" in result["message"].lower()
    
    def test_move_boundary_top(self, game_service, test_user, db_session):
        """Test movement at top boundary"""
        game_state = GameState(
            user_id=test_user.id,
            position_x=32,
            position_y=0,
            health=100,
            max_health=100
        )
        db_session.add(game_state)
        db_session.commit()
        
        result = game_service.execute_command("move up", test_user.id)
        
        assert result["success"] is True
        assert result["game_state"]["position_y"] == 0
        assert "boundary" in result["message"].lower()
    
    def test_move_boundary_bottom(self, game_service, test_user, db_session):
        """Test movement at bottom boundary"""
        game_state = GameState(
            user_id=test_user.id,
            position_x=32,
            position_y=GRID_SIZE - 1,
            health=100,
            max_health=100
        )
        db_session.add(game_state)
        db_session.commit()
        
        result = game_service.execute_command("move down", test_user.id)
        
        assert result["success"] is True
        assert result["game_state"]["position_y"] == GRID_SIZE - 1
        assert "boundary" in result["message"].lower()
    
    def test_move_boundary_left(self, game_service, test_user, db_session):
        """Test movement at left boundary"""
        game_state = GameState(
            user_id=test_user.id,
            position_x=0,
            position_y=32,
            health=100,
            max_health=100
        )
        db_session.add(game_state)
        db_session.commit()
        
        result = game_service.execute_command("move left", test_user.id)
        
        assert result["success"] is True
        assert result["game_state"]["position_x"] == 0
        assert "boundary" in result["message"].lower()
    
    def test_move_boundary_right(self, game_service, test_user, db_session):
        """Test movement at right boundary"""
        game_state = GameState(
            user_id=test_user.id,
            position_x=GRID_SIZE - 1,
            position_y=32,
            health=100,
            max_health=100
        )
        db_session.add(game_state)
        db_session.commit()
        
        result = game_service.execute_command("move right", test_user.id)
        
        assert result["success"] is True
        assert result["game_state"]["position_x"] == GRID_SIZE - 1
        assert "boundary" in result["message"].lower()


class TestCombat:
    """Test combat commands"""
    
    def test_attack_another_user(self, game_service, test_user, test_user2, db_session):
        """Test attacking another user"""
        # Create game states for both users
        attacker_state = GameState(
            user_id=test_user.id,
            position_x=32,
            position_y=32,
            health=100,
            max_health=100
        )
        target_state = GameState(
            user_id=test_user2.id,
            position_x=33,
            position_y=32,
            health=100,
            max_health=100
        )
        db_session.add_all([attacker_state, target_state])
        db_session.commit()
        
        result = game_service.execute_command("attack", test_user.id, test_user2.username)
        
        assert result["success"] is True
        assert result["game_state"]["health"] == 100 - ATTACK_DAMAGE
        assert "attacked" in result["message"].lower()
    
    def test_attack_self_fails(self, game_service, test_user, db_session):
        """Test that attacking oneself fails"""
        game_state = GameState(
            user_id=test_user.id,
            position_x=32,
            position_y=32,
            health=100,
            max_health=100
        )
        db_session.add(game_state)
        db_session.commit()
        
        result = game_service.execute_command("attack", test_user.id)
        
        assert result["success"] is False
        assert "cannot attack yourself" in result["error"].lower()
    
    def test_attack_nonexistent_user(self, game_service, test_user, db_session):
        """Test attacking a non-existent user"""
        game_state = GameState(
            user_id=test_user.id,
            position_x=32,
            position_y=32,
            health=100,
            max_health=100
        )
        db_session.add(game_state)
        db_session.commit()
        
        result = game_service.execute_command("attack", test_user.id, "nonexistent")
        
        assert result["success"] is False
        assert "not found" in result["error"].lower()
    
    def test_attack_until_defeated(self, game_service, test_user, test_user2, db_session):
        """Test attacking until target is defeated"""
        attacker_state = GameState(
            user_id=test_user.id,
            position_x=32,
            position_y=32,
            health=100,
            max_health=100
        )
        target_state = GameState(
            user_id=test_user2.id,
            position_x=33,
            position_y=32,
            health=15,
            max_health=100
        )
        db_session.add_all([attacker_state, target_state])
        db_session.commit()
        
        result = game_service.execute_command("attack", test_user.id, test_user2.username)
        
        assert result["success"] is True
        assert result["game_state"]["health"] == 5
        
        # Attack again to defeat
        result = game_service.execute_command("attack", test_user.id, test_user2.username)
        
        assert result["success"] is True
        assert result["game_state"]["health"] == 0
        assert "defeated" in result["message"].lower()


class TestHealing:
    """Test healing commands"""
    
    def test_heal_damaged_user(self, game_service, test_user, db_session):
        """Test healing a damaged user"""
        game_state = GameState(
            user_id=test_user.id,
            position_x=32,
            position_y=32,
            health=50,
            max_health=100
        )
        db_session.add(game_state)
        db_session.commit()
        
        result = game_service.execute_command("heal", test_user.id)
        
        assert result["success"] is True
        assert result["game_state"]["health"] == 50 + HEAL_AMOUNT
        assert "healed" in result["message"].lower()
    
    def test_heal_capped_at_max(self, game_service, test_user, db_session):
        """Test that healing doesn't exceed max health"""
        game_state = GameState(
            user_id=test_user.id,
            position_x=32,
            position_y=32,
            health=95,
            max_health=100
        )
        db_session.add(game_state)
        db_session.commit()
        
        result = game_service.execute_command("heal", test_user.id)
        
        assert result["success"] is True
        assert result["game_state"]["health"] == 100
        assert "healed for 5" in result["message"].lower()


class TestCommandParsing:
    """Test command parsing"""
    
    def test_parse_move_up(self, game_service):
        """Test parsing move up command"""
        parsed = game_service.parse_command("move up")
        assert parsed == ("move up", None)
    
    def test_parse_attack_with_mention(self, game_service):
        """Test parsing attack with @mention"""
        parsed = game_service.parse_command("attack @player2")
        assert parsed == ("attack", "player2")
    
    def test_parse_invalid_command(self, game_service):
        """Test parsing invalid command"""
        parsed = game_service.parse_command("invalid command")
        assert parsed is None
    
    def test_parse_case_insensitive(self, game_service):
        """Test that parsing is case-insensitive"""
        parsed = game_service.parse_command("MOVE UP")
        assert parsed == ("move up", None)
