#!/usr/bin/env python3
"""Test script for TD-5 Admin Allowlist implementation."""

import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.core.admin import get_admin_allowlist, is_user_admin

def test_allowlist_parsing():
    """Test that allowlist is parsed correctly."""
    print("\n=== Test 1: Allowlist Parsing ===")
    
    # Temporarily override the cached value
    from src.core import admin
    admin._get_admin_allowlist.cache_clear()
    
    # Test with a known value
    from src.core.config import settings
    original = settings.ADMIN_ALLOWLIST
    settings.ADMIN_ALLOWLIST = "Alice;BOB;charlie"
    
    allowlist = get_admin_allowlist()
    
    # Restore
    settings.ADMIN_ALLOWLIST = original
    admin._get_admin_allowlist.cache_clear()
    
    expected = {"alice", "bob", "charlie"}
    if allowlist == expected:
        print(f"✓ Allowlist parsed correctly: {allowlist}")
        return True
    else:
        print(f"✗ Expected {expected}, got {allowlist}")
        return False

def test_case_insensitive_check():
    """Test that admin check is case-insensitive."""
    print("\n=== Test 2: Case Insensitive Check ===")
    
    from src.core import admin
    admin._get_admin_allowlist.cache_clear()
    
    from src.core.config import settings
    original = settings.ADMIN_ALLOWLIST
    settings.ADMIN_ALLOWLIST = "Admina"
    
    # Test various cases
    tests = [
        ("admina", True),
        ("Admina", True),
        ("ADMINA", True),
        ("hacker", False),
        ("ADMIN", False),
    ]
    
    all_passed = True
    for username, expected in tests:
        result = is_user_admin(username)
        status = "✓" if result == expected else "✗"
        print(f"  {status} {username}: {result} (expected {expected})")
        if result != expected:
            all_passed = False
    
    # Restore
    settings.ADMIN_ALLOWLIST = original
    admin._get_admin_allowlist.cache_clear()
    
    return all_passed

def test_empty_allowlist():
    """Test that empty allowlist defaults to 'admina'."""
    print("\n=== Test 3: Empty Allowlist Default ===")
    
    from src.core import admin
    admin._get_admin_allowlist.cache_clear()
    
    from src.core.config import settings
    original = settings.ADMIN_ALLOWLIST
    settings.ADMIN_ALLOWLIST = ""
    
    allowlist = get_admin_allowlist()
    
    # Restore
    settings.ADMIN_ALLOWLIST = original
    admin._get_admin_allowlist.cache_clear()
    
    if "admina" in allowlist:
        print(f"✓ Default 'admina' present in empty allowlist: {allowlist}")
        return True
    else:
        print(f"✗ 'admina' not found in: {allowlist}")
        return False

def main():
    print("=" * 60)
    print("TD-5 Admin Allowlist Tests")
    print("=" * 60)
    
    all_passed = True
    
    if not test_allowlist_parsing():
        all_passed = False
    
    if not test_case_insensitive_check():
        all_passed = False
    
    if not test_empty_allowlist():
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
