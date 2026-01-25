#!/usr/bin/env python3
"""
Migration script to add hash_type column to users table.
This is for the bcrypt-only password hashing migration.

Existing users will have hash_type=NULL, which forces them to reset their password.
New users will have hash_type='bcrypt'.
"""

import sqlite3
import os

def migrate_add_hash_type():
    # Path to the database (relative to backend directory where script is run from)
    db_path = 'chat.db'
    
    if not os.path.exists(db_path):
        print(f"Database not found at {os.path.abspath(db_path)}")
        print("Please run this script from the backend directory.")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check if hash_type column already exists
    cursor.execute("PRAGMA table_info(users)")
    columns = [column[1] for column in cursor.fetchall()]
    
    if 'hash_type' in columns:
        print("hash_type column already exists. Skipping migration.")
        conn.close()
        return
    
    # Add hash_type column
    print("Adding hash_type column to users table...")
    cursor.execute("ALTER TABLE users ADD COLUMN hash_type VARCHAR(20)")
    
    # The column is NULL by default, which is what we want for legacy users
    # They will be forced to reset their password
    
    conn.commit()
    conn.close()
    print("Migration completed successfully!")
    print("Existing users (hash_type=NULL) will need to reset their password.")
    print("New users will be assigned hash_type='bcrypt'.")

if __name__ == "__main__":
    migrate_add_hash_type()
