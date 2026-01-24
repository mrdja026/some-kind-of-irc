from src.core.database import SessionLocal
from src.models.user import User
from src.api.endpoints.auth import get_password_hash

def create_test_user():
    # Create a new session
    db = SessionLocal()
    
    # Check if test user already exists
    existing_user = db.query(User).filter(User.username == 'testuser22').first()
    if existing_user:
        print('Test user already exists')
        return
    
    # Create a new test user
    new_user = User(
        username='testuser22',
        password_hash=get_password_hash('pass123')
    )
    
    # Add and commit the new user
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    print(f'Test user created successfully. ID: {new_user.id}')
    
    # Create another test user
    existing_user2 = db.query(User).filter(User.username == 'testuser2').first()
    if existing_user2:
        print('Second test user already exists')
        return
    
    new_user2 = User(
        username='testuser2',
        password_hash=get_password_hash('pass456')
    )
    
    db.add(new_user2)
    db.commit()
    db.refresh(new_user2)
    
    print(f'Second test user created successfully. ID: {new_user2.id}')

if __name__ == "__main__":
    create_test_user()