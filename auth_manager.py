"""
Authentication manager for user login and registration
"""

import bcrypt
import uuid
from typing import Optional
from db_manager import DatabaseManager
import mysql.connector
from mysql.connector import Error

class AuthManager:
    """Handles user authentication and management"""

    def __init__(self):
        self.db = DatabaseManager()

    def hash_password(self, password: str) -> str:
        """Hash a password with bcrypt (per-hash random salt)."""
        return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    def verify_password(self, password: str, password_hash: str) -> bool:
        """Constant-time bcrypt verification."""
        try:
            return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
        except (ValueError, TypeError):
            return False

    def create_user(self, username: str, password: str) -> bool:
        """Create a new user account"""
        connection = self.db.get_connection()
        if not connection:
            return False

        cursor = connection.cursor()

        try:
            cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
            if cursor.fetchone():
                cursor.close()
                return False  # Username already exists

            user_id = str(uuid.uuid4())
            password_hash = self.hash_password(password)

            cursor.execute(
                """
                INSERT INTO users (id, username, password_hash, is_active)
                VALUES (%s, %s, %s, %s)
                """,
                (user_id, username, password_hash, True),
            )

            cursor.close()
            return True

        except Error as e:
            cursor.close()
            print(f"Error creating user: {e}")
            return False

    def authenticate_user(self, username: str, password: str) -> Optional[str]:
        """Authenticate user and return user ID if successful"""
        connection = self.db.get_connection()
        if not connection:
            return None

        cursor = connection.cursor()

        try:
            cursor.execute(
                """
                SELECT id, password_hash FROM users
                WHERE username = %s AND is_active = TRUE
                """,
                (username,),
            )

            row = cursor.fetchone()
            cursor.close()

            if not row:
                return None

            user_id, stored_hash = row
            if self.verify_password(password, stored_hash):
                return user_id
            return None

        except Error as e:
            cursor.close()
            print(f"Error authenticating user: {e}")
            return None

    def get_user_info(self, user_id: str) -> Optional[dict]:
        """Get user information"""
        connection = self.db.get_connection()
        if not connection:
            return None

        cursor = connection.cursor()

        try:
            cursor.execute(
                """
                SELECT id, username, created_at, is_active
                FROM users
                WHERE id = %s
                """,
                (user_id,),
            )

            row = cursor.fetchone()
            if row:
                result = {
                    "id": row[0],
                    "username": row[1],
                    "created_at": row[2],
                    "is_active": row[3],
                }
                cursor.close()
                return result

            cursor.close()
            return None

        except Error as e:
            cursor.close()
            print(f"Error getting user info: {e}")
            return None

    def deactivate_user(self, user_id: str) -> bool:
        """Deactivate a user account"""
        connection = self.db.get_connection()
        if not connection:
            return False

        cursor = connection.cursor()

        try:
            cursor.execute(
                "UPDATE users SET is_active = FALSE WHERE id = %s",
                (user_id,),
            )

            cursor.close()
            return True

        except Error as e:
            cursor.close()
            print(f"Error deactivating user: {e}")
            return False

    def change_password(self, user_id: str, old_password: str, new_password: str) -> bool:
        """Change user password"""
        connection = self.db.get_connection()
        if not connection:
            return False

        cursor = connection.cursor()

        try:
            cursor.execute(
                "SELECT password_hash FROM users WHERE id = %s",
                (user_id,),
            )
            row = cursor.fetchone()

            if not row or not self.verify_password(old_password, row[0]):
                cursor.close()
                return False  # Old password incorrect

            new_password_hash = self.hash_password(new_password)
            cursor.execute(
                "UPDATE users SET password_hash = %s WHERE id = %s",
                (new_password_hash, user_id),
            )

            cursor.close()
            return True

        except Error as e:
            cursor.close()
            print(f"Error changing password: {e}")
            return False
