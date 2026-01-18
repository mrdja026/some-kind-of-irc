from fastapi.testclient import TestClient
from src.main import app
from src.core.database import Base, get_db
from src.core.database import engine

# Create all tables
Base.metadata.create_all(bind=engine)

# Create test client
client = TestClient(app)

# Test data
test_user = {'username': 'testuser1', 'password': 'pass123'}

# Test register endpoint
print('Testing register endpoint...')
response = client.post('/auth/register', json=test_user)
print(f'Status code: {response.status_code}')
print(f'Response: {response.json()}')

# Test login endpoint
print('\nTesting login endpoint...')
response = client.post('/auth/login', data={'username': test_user['username'], 'password': test_user['password']})
print(f'Status code: {response.status_code}')
print(f'Response: {response.json()}')
