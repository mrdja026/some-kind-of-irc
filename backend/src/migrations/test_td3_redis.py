#!/usr/bin/env python3
"""Test script for TD-3 Redis Pub/Sub implementation."""

import json
import redis
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.services.event_publisher import publish_user_registered, get_redis_client
from src.core.config import settings

def test_redis_connection():
    """Test Redis connection."""
    print("\n=== Test 1: Redis Connection ===")
    try:
        client = get_redis_client()
        client.ping()
        print("✓ Redis connection successful")
        return True
    except Exception as e:
        print(f"✗ Redis connection failed: {e}")
        print("  Make sure Redis is running: docker-compose up -d redis")
        return False

def test_publish_event():
    """Test publishing user.registered event."""
    print("\n=== Test 2: Publish Event ===")
    try:
        result = publish_user_registered(99999, "testuser_td3")
        if result:
            print("✓ Event published successfully")
            return True
        else:
            print("✗ Event publish returned False")
            return False
    except Exception as e:
        print(f"✗ Failed to publish event: {e}")
        return False

def test_subscribe_and_receive():
    """Test subscribing and receiving events."""
    print("\n=== Test 3: Subscribe and Receive ===")
    try:
        client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
        pubsub = client.pubsub()
        pubsub.subscribe("user.events")
        
        # Publish a test event
        test_event = {
            "event_type": "user.registered",
            "user_id": 88888,
            "username": "test_subscriber",
            "timestamp": "2025-01-01T00:00:00"
        }
        client.publish("user.events", json.dumps(test_event))
        
        # Listen for message (timeout after 2 seconds)
        import time
        start = time.time()
        received = False
        
        for message in pubsub.listen():
            if message["type"] == "message":
                data = json.loads(message["data"])
                if data["user_id"] == 88888:
                    print(f"✓ Received event: {data}")
                    received = True
                    break
            if time.time() - start > 2:
                break
        
        pubsub.unsubscribe()
        pubsub.close()
        
        if not received:
            print("✗ Did not receive test event within 2 seconds")
            return False
        
        return True
    except Exception as e:
        print(f"✗ Subscribe test failed: {e}")
        return False

def main():
    print("=" * 60)
    print("TD-3 Redis Pub/Sub Test")
    print("=" * 60)
    
    all_passed = True
    
    if not test_redis_connection():
        all_passed = False
        print("\n⚠️  Skipping remaining tests (Redis not available)")
        return 1
    
    if not test_publish_event():
        all_passed = False
    
    if not test_subscribe_and_receive():
        all_passed = False
    
    print("\n" + "=" * 60)
    if all_passed:
        print("✓ All tests passed!")
    else:
        print("✗ Some tests failed")
    print("=" * 60)
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())
