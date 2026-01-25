#!/usr/bin/env python3
"""
Test script to verify bcrypt-only password hashing migration.
"""

import requests
import sqlite3
import sys
import os

BASE_URL = "http://localhost:8000"

def test_new_user_registration():
    """Test that new users can register with bcrypt."""
    print("\n=== Test 1: New User Registration with bcrypt ===")
    
    # Generate unique username
    import time
    username = f"testuser_{int(time.time())}"
    password = "testpassword123"
    
    # Register new user
    response = requests.post(
        f"{BASE_URL}/auth/register",
        json={"username": username, "password": password}
    )
    
    if response.status_code == 200:
        print(f"✓ Registration successful for user: {username}")
        
        # Verify hash_type is set to 'bcrypt' in database
        conn = sqlite3.connect('chat.db')
        cursor = conn.cursor()
        cursor.execute("SELECT hash_type FROM users WHERE username = ?", (username,))
        result = cursor.fetchone()
        conn.close()
        
        if result and result[0] == 'bcrypt':
            print(f"✓ hash_type correctly set to 'bcrypt' in database")
            return username, password
        else:
            print(f"✗ hash_type not set correctly: {result}")
            return None, None
    else:
        print(f"✗ Registration failed: {response.status_code} - {response.text}")
        return None, None

def test_new_user_login(username, password):
    """Test that new bcrypt users can login."""
    print(f"\n=== Test 2: Login with bcrypt user ({username}) ===")
    
    response = requests.post(
        f"{BASE_URL}/auth/login",
        data={"username": username, "password": password}
    )
    
    if response.status_code == 200:
        print("✓ Login successful for bcrypt user")
        return True
    else:
        print(f"✗ Login failed: {response.status_code} - {response.text}")
        return False

def test_legacy_user_blocked():
    """Test that legacy users (hash_type=NULL) are blocked."""
    print("\n=== Test 3: Legacy user login blocked ===")
    
    # Find a legacy user (hash_type is NULL)
    conn = sqlite3.connect('chat.db')
    cursor = conn.cursor()
    cursor.execute("SELECT username FROM users WHERE hash_type IS NULL LIMIT 1")
    result = cursor.fetchone()
    conn.close()
    
    if not result:
        print("ℹ No legacy users found to test (all users already migrated)")
        return True
    
    legacy_username = result[0]
    print(f"Testing legacy user: {legacy_username}")
    
    # Try to login as legacy user
    response = requests.post(
        f"{BASE_URL}/auth/login",
        data={"username": legacy_username, "password": "anypassword"}
    )
    
    if response.status_code == 401 and "Password reset required" in response.text:
        print("✓ Legacy user correctly blocked with 'Password reset required' message")
        return True
    else:
        print(f"✗ Legacy user not handled correctly: {response.status_code} - {response.text}")
        return False

def test_password_hash_format():
    """Test that password hashes are in bcrypt format."""
    print("\n=== Test 4: Verify bcrypt hash format ===")
    
    conn = sqlite3.connect('chat.db')
    cursor = conn.cursor()
    cursor.execute("SELECT username, password_hash FROM users WHERE hash_type = 'bcrypt' LIMIT 1")
    result = cursor.fetchone()
    conn.close()
    
    if not result:
        print("ℹ No bcrypt users found to verify")
        return True
    
    username, password_hash = result
    
    # Check if hash starts with bcrypt identifier
    if password_hash.startswith('$2'):
        print(f"✓ Password hash for {username} is in bcrypt format")
        print(f"  Hash preview: {password_hash[:30]}...")
        return True
    else:
        print(f"✗ Password hash for {username} is NOT in bcrypt format: {password_hash[:30]}...")
        return False

def main():
    print("=" * 60)
    print("Bcrypt-Only Password Hashing Migration Test")
    print("=" * 60)
    
    # Check if backend is running
    try:
        response = requests.get(f"{BASE_URL}/docs", timeout=2)
    except requests.exceptions.ConnectionError:
        print("\n✗ Backend is not running. Please start it first:")
        print("   cd backend && python -m uvicorn src.main:app --reload")
        sys.exit(1)
    
    print("\n✓ Backend is running")
    
    # Run tests
    all_passed = True
    
    # Test 1: New user registration
    username, password = test_new_user_registration()
    if not username:
        all_passed = False
    
    # Test 2: Login with new user
    if username and password:
        if not test_new_user_login(username, password):
            all_passed = False
    
    # Test 3: Legacy user blocked
    if not test_legacy_user_blocked():
        all_passed = False
    
    # Test 4: Hash format verification
    if not test_password_hash_format():
        all_passed = False
    
    # Summary
    print("\n" + "=" * 60)
    if all_passed:
        print("✓ All tests passed!")
    else:
        print("✗ Some tests failed")
    print("=" * 60)
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())
