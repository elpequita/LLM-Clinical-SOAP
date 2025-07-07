"""
User Account Management Script
Handles activation/deactivation of individual user accounts
"""

import json
import mysql.connector
from mysql.connector import Error
from datetime import datetime
from typing import Optional, List, Dict

class UserAccountManager:
    """Manage user account activation/deactivation"""
    
    def __init__(self, config_file: str = "db_config.json"):
        self.config_file = config_file
        self.config = self.load_config()
    
    def load_config(self) -> Dict:
        """Load database configuration"""
        try:
            with open(self.config_file, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return {
                "host": "localhost",
                "port": 3306,
                "user": "clinical_user",
                "password": "clinical_password",
                "database": "clinical_docs"
            }
    
    def get_connection(self):
        """Get database connection"""
        try:
            connection = mysql.connector.connect(
                host=self.config['host'],
                port=self.config['port'],
                user=self.config['user'],
                password=self.config['password'],
                database=self.config['database']
            )
            return connection
        except Error as e:
            print(f"❌ Database connection error: {e}")
            return None
    
    def list_users(self) -> List[Dict]:
        """List all users with their status"""
        print("👥 USER ACCOUNTS")
        print("=" * 50)
        
        connection = self.get_connection()
        if not connection:
            return []
        
        cursor = connection.cursor()
        try:
            cursor.execute("""
                SELECT id, username, created_at, is_active
                FROM users 
                ORDER BY created_at DESC
            """)
            users = cursor.fetchall()
            
            user_list = []
            for i, user in enumerate(users, 1):
                status = "🟢 ACTIVE" if user[3] else "🔴 INACTIVE"
                print(f"{i}. Username: {user[1]}")
                print(f"   ID: {user[0]}")
                print(f"   Created: {user[2]}")
                print(f"   Status: {status}")
                print()
                
                user_list.append({
                    'id': user[0],
                    'username': user[1],
                    'created_at': user[2],
                    'is_active': user[3]
                })
            
            if not users:
                print("⚠️ No users found in database")
            
            cursor.close()
            connection.close()
            return user_list
            
        except Error as e:
            print(f"❌ Error listing users: {e}")
            cursor.close()
            connection.close()
            return []
    
    def deactivate_user(self, username: str) -> bool:
        """Deactivate a user account"""
        print(f"🔴 DEACTIVATING USER: {username}")
        print("-" * 40)
        
        connection = self.get_connection()
        if not connection:
            return False
        
        cursor = connection.cursor()
        try:
            # Check if user exists and is active
            cursor.execute("SELECT id, is_active FROM users WHERE username = %s", (username,))
            user = cursor.fetchone()
            
            if not user:
                print(f"❌ User '{username}' not found")
                return False
            
            if not user[1]:
                print(f"⚠️ User '{username}' is already inactive")
                return True
            
            # Deactivate user
            cursor.execute("""
                UPDATE users 
                SET is_active = FALSE 
                WHERE username = %s
            """, (username,))
            
            connection.commit()
            print(f"✅ User '{username}' has been deactivated")
            print(f"   - User ID: {user[0]}")
            print(f"   - Status changed: ACTIVE → INACTIVE")
            print(f"   - User will not be able to login")
            print(f"   - User data remains in database")
            
            cursor.close()
            connection.close()
            return True
            
        except Error as e:
            print(f"❌ Error deactivating user: {e}")
            cursor.close()
            connection.close()
            return False
    
    def activate_user(self, username: str) -> bool:
        """Activate a user account"""
        print(f"🟢 ACTIVATING USER: {username}")
        print("-" * 40)
        
        connection = self.get_connection()
        if not connection:
            return False
        
        cursor = connection.cursor()
        try:
            # Check if user exists
            cursor.execute("SELECT id, is_active FROM users WHERE username = %s", (username,))
            user = cursor.fetchone()
            
            if not user:
                print(f"❌ User '{username}' not found")
                return False
            
            if user[1]:
                print(f"⚠️ User '{username}' is already active")
                return True
            
            # Activate user
            cursor.execute("""
                UPDATE users 
                SET is_active = TRUE 
                WHERE username = %s
            """, (username,))
            
            connection.commit()
            print(f"✅ User '{username}' has been activated")
            print(f"   - User ID: {user[0]}")
            print(f"   - Status changed: INACTIVE → ACTIVE")
            print(f"   - User can now login normally")
            
            cursor.close()
            connection.close()
            return True
            
        except Error as e:
            print(f"❌ Error activating user: {e}")
            cursor.close()
            connection.close()
            return False
    
    def get_user_stats(self, username: str) -> Optional[Dict]:
        """Get detailed user statistics"""
        connection = self.get_connection()
        if not connection:
            return None
        
        cursor = connection.cursor()
        try:
            # Get user info
            cursor.execute("""
                SELECT id, username, created_at, is_active
                FROM users 
                WHERE username = %s
            """, (username,))
            user = cursor.fetchone()
            
            if not user:
                return None
            
            # Get transcription count
            cursor.execute("""
                SELECT COUNT(*) FROM transcriptions WHERE user_id = %s
            """, (user[0],))
            transcription_count = cursor.fetchone()[0]
            
            # Get SOAP note count
            cursor.execute("""
                SELECT COUNT(*) FROM transcriptions 
                WHERE user_id = %s AND soap_note IS NOT NULL AND soap_note != '{}'
            """, (user[0],))
            soap_count = cursor.fetchone()[0]
            
            # Get last activity
            cursor.execute("""
                SELECT MAX(created_at) FROM transcriptions WHERE user_id = %s
            """, (user[0],))
            last_activity = cursor.fetchone()[0]
            
            stats = {
                'id': user[0],
                'username': user[1],
                'created_at': user[2],
                'is_active': user[3],
                'transcription_count': transcription_count,
                'soap_count': soap_count,
                'last_activity': last_activity
            }
            
            cursor.close()
            connection.close()
            return stats
            
        except Error as e:
            print(f"❌ Error getting user stats: {e}")
            cursor.close()
            connection.close()
            return None
    
    def bulk_deactivate_users(self, usernames: List[str]) -> Dict[str, bool]:
        """Deactivate multiple users"""
        print(f"🔴 BULK DEACTIVATING {len(usernames)} USERS")
        print("=" * 50)
        
        results = {}
        for username in usernames:
            results[username] = self.deactivate_user(username)
            print()
        
        return results
    
    def interactive_management(self):
        """Interactive user management"""
        print("🏥 CLINICAL DOCUMENTATION AI - USER ACCOUNT MANAGEMENT")
        print("=" * 60)
        
        while True:
            print("\n📋 OPTIONS:")
            print("1. List all users")
            print("2. Deactivate user")
            print("3. Activate user")
            print("4. View user details")
            print("5. Bulk deactivate")
            print("6. Exit")
            
            try:
                choice = input("\nEnter choice (1-6): ").strip()
                
                if choice == "1":
                    self.list_users()
                
                elif choice == "2":
                    username = input("Enter username to deactivate: ").strip()
                    if username:
                        self.deactivate_user(username)
                
                elif choice == "3":
                    username = input("Enter username to activate: ").strip()
                    if username:
                        self.activate_user(username)
                
                elif choice == "4":
                    username = input("Enter username for details: ").strip()
                    if username:
                        stats = self.get_user_stats(username)
                        if stats:
                            print(f"\n📊 USER DETAILS: {username}")
                            print("-" * 30)
                            print(f"ID: {stats['id']}")
                            print(f"Created: {stats['created_at']}")
                            print(f"Status: {'🟢 ACTIVE' if stats['is_active'] else '🔴 INACTIVE'}")
                            print(f"Transcriptions: {stats['transcription_count']}")
                            print(f"SOAP Notes: {stats['soap_count']}")
                            print(f"Last Activity: {stats['last_activity'] or 'Never'}")
                        else:
                            print(f"❌ User '{username}' not found")
                
                elif choice == "5":
                    usernames_input = input("Enter usernames separated by commas: ").strip()
                    if usernames_input:
                        usernames = [u.strip() for u in usernames_input.split(",")]
                        self.bulk_deactivate_users(usernames)
                
                elif choice == "6":
                    print("👋 Goodbye!")
                    break
                
                else:
                    print("❌ Invalid choice")
                
            except KeyboardInterrupt:
                print("\n👋 Goodbye!")
                break
            except Exception as e:
                print(f"❌ Error: {e}")

def main():
    """Main function"""
    manager = UserAccountManager()
    manager.interactive_management()

if __name__ == "__main__":
    main()