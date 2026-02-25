#!/usr/bin/env python3
"""
Migration script to add gmail_tokens table for Gmail OAuth storage.
"""

import os
import sqlite3


def migrate_add_gmail_tokens():
    db_path = "chat.db"

    if not os.path.exists(db_path):
        print(f"Database not found at {os.path.abspath(db_path)}")
        print("Please run this script from the backend directory.")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='gmail_tokens'"
    )
    if cursor.fetchone():
        print("gmail_tokens table already exists. Skipping migration.")
        conn.close()
        return

    print("Creating gmail_tokens table...")
    cursor.execute(
        """
        CREATE TABLE gmail_tokens (
            id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL UNIQUE,
            access_token TEXT,
            refresh_token TEXT NOT NULL,
            token_type TEXT,
            scope TEXT,
            expires_at DATETIME,
            created_at DATETIME,
            updated_at DATETIME,
            FOREIGN KEY(user_id) REFERENCES users (id)
        )
        """
    )

    conn.commit()
    conn.close()
    print("Migration completed successfully!")


if __name__ == "__main__":
    migrate_add_gmail_tokens()
