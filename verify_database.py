"""
Database verification script for Clinical Documentation AI
This script helps verify that data is being entered correctly into MySQL
"""

import json
import mysql.connector
from mysql.connector import Error
from datetime import datetime
from typing import Dict, List
import uuid

class DatabaseVerifier:
    """Verify database operations and data integrity"""
    
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
    
    def verify_connection(self):
        """Verify database connection"""
        print("🔗 Testing Database Connection")
        print("-" * 40)
        
        connection = self.get_connection()
        if connection and connection.is_connected():
            print("✅ MySQL connection successful")
            
            # Get database info
            cursor = connection.cursor()
            cursor.execute("SELECT DATABASE()")
            db_name = cursor.fetchone()[0]
            print(f"✅ Connected to database: {db_name}")
            
            cursor.execute("SELECT VERSION()")
            version = cursor.fetchone()[0]
            print(f"✅ MySQL version: {version}")
            
            cursor.close()
            connection.close()
            return True
        else:
            print("❌ Database connection failed")
            return False
    
    def verify_tables(self):
        """Verify that all required tables exist"""
        print("\n📋 Verifying Database Tables")
        print("-" * 40)
        
        connection = self.get_connection()
        if not connection:
            return False
        
        cursor = connection.cursor()
        
        # Check required tables
        required_tables = ['users', 'transcriptions', 'app_settings']
        
        cursor.execute("SHOW TABLES")
        existing_tables = [table[0] for table in cursor.fetchall()]
        
        all_exist = True
        for table in required_tables:
            if table in existing_tables:
                print(f"✅ Table '{table}' exists")
            else:
                print(f"❌ Table '{table}' missing")
                all_exist = False
        
        # Show table structures
        for table in existing_tables:
            if table in required_tables:
                print(f"\n📊 Structure of '{table}' table:")
                cursor.execute(f"DESCRIBE {table}")
                columns = cursor.fetchall()
                for column in columns:
                    print(f"   {column[0]} | {column[1]} | {column[2]} | {column[3]}")
        
        cursor.close()
        connection.close()
        return all_exist
    
    def verify_settings(self):
        """Verify app settings"""
        print("\n⚙️ Verifying App Settings")
        print("-" * 40)
        
        connection = self.get_connection()
        if not connection:
            return False
        
        cursor = connection.cursor()
        
        try:
            cursor.execute("SELECT setting_key, setting_value FROM app_settings")
            settings = cursor.fetchall()
            
            if settings:
                print("✅ App settings found:")
                for key, value in settings:
                    print(f"   {key}: {value}")
            else:
                print("⚠️ No app settings found")
            
            cursor.close()
            connection.close()
            return True
            
        except Error as e:
            print(f"❌ Error checking settings: {e}")
            cursor.close()
            connection.close()
            return False
    
    def view_users(self):
        """View all users in the database"""
        print("\n👥 Database Users")
        print("-" * 40)
        
        connection = self.get_connection()
        if not connection:
            return False
        
        cursor = connection.cursor()
        
        try:
            cursor.execute("""
                SELECT id, username, created_at, is_active 
                FROM users 
                ORDER BY created_at DESC
            """)
            users = cursor.fetchall()
            
            if users:
                print(f"✅ Found {len(users)} users:")
                for user in users:
                    status = "Active" if user[3] else "Inactive"
                    print(f"   ID: {user[0]}")
                    print(f"   Username: {user[1]}")
                    print(f"   Created: {user[2]}")
                    print(f"   Status: {status}")
                    print()
            else:
                print("⚠️ No users found in database")
            
            cursor.close()
            connection.close()
            return True
            
        except Error as e:
            print(f"❌ Error viewing users: {e}")
            cursor.close()
            connection.close()
            return False
    
    def view_transcriptions(self, limit: int = 10):
        """View recent transcriptions"""
        print(f"\n📝 Recent Transcriptions (Last {limit})")
        print("-" * 40)
        
        connection = self.get_connection()
        if not connection:
            return False
        
        cursor = connection.cursor()
        
        try:
            cursor.execute("""
                SELECT t.id, t.filename, t.transcription_text, t.language, 
                       t.created_at, t.status, u.username
                FROM transcriptions t
                JOIN users u ON t.user_id = u.id
                ORDER BY t.created_at DESC
                LIMIT %s
            """, (limit,))
            transcriptions = cursor.fetchall()
            
            if transcriptions:
                print(f"✅ Found {len(transcriptions)} transcriptions:")
                for trans in transcriptions:
                    print(f"   ID: {trans[0]}")
                    print(f"   File: {trans[1]}")
                    print(f"   User: {trans[6]}")
                    print(f"   Language: {trans[3]}")
                    print(f"   Status: {trans[5]}")
                    print(f"   Created: {trans[4]}")
                    print(f"   Text: {trans[2][:100]}..." if len(trans[2]) > 100 else f"   Text: {trans[2]}")
                    print()
            else:
                print("⚠️ No transcriptions found in database")
            
            cursor.close()
            connection.close()
            return True
            
        except Error as e:
            print(f"❌ Error viewing transcriptions: {e}")
            cursor.close()
            connection.close()
            return False
    
    def view_soap_notes(self, limit: int = 5):
        """View SOAP notes from transcriptions"""
        print(f"\n🏥 SOAP Notes (Last {limit})")
        print("-" * 40)
        
        connection = self.get_connection()
        if not connection:
            return False
        
        cursor = connection.cursor()
        
        try:
            cursor.execute("""
                SELECT t.id, t.filename, t.soap_note, u.username, t.created_at
                FROM transcriptions t
                JOIN users u ON t.user_id = u.id
                WHERE t.soap_note IS NOT NULL AND t.soap_note != '{}'
                ORDER BY t.created_at DESC
                LIMIT %s
            """, (limit,))
            soap_notes = cursor.fetchall()
            
            if soap_notes:
                print(f"✅ Found {len(soap_notes)} SOAP notes:")
                for note in soap_notes:
                    print(f"\n   📄 {note[1]} (User: {note[3]})")
                    print(f"   Created: {note[4]}")
                    
                    try:
                        soap_data = json.loads(note[2])
                        print(f"   SUBJECTIVE: {soap_data.get('subjective', 'N/A')[:80]}...")
                        print(f"   OBJECTIVE: {soap_data.get('objective', 'N/A')[:80]}...")
                        print(f"   ASSESSMENT: {soap_data.get('assessment', 'N/A')[:80]}...")
                        print(f"   PLAN: {soap_data.get('plan', 'N/A')[:80]}...")
                    except json.JSONDecodeError:
                        print(f"   SOAP Data: {note[2][:100]}...")
            else:
                print("⚠️ No SOAP notes found in database")
            
            cursor.close()
            connection.close()
            return True
            
        except Error as e:
            print(f"❌ Error viewing SOAP notes: {e}")
            cursor.close()
            connection.close()
            return False
    
    def create_test_data(self):
        """Create test data for verification"""
        print("\n🧪 Creating Test Data")
        print("-" * 40)
        
        try:
            from auth_manager import AuthManager
            from db_manager import DatabaseManager
            
            # Create test user
            auth = AuthManager()
            username = f"test_user_{int(datetime.now().timestamp())}"
            password = "test123"
            
            if auth.create_user(username, password):
                print(f"✅ Test user created: {username}")
                
                # Authenticate to get user ID
                user_id = auth.authenticate_user(username, password)
                if user_id:
                    print(f"✅ User authenticated, ID: {user_id}")
                    
                    # Create test transcription
                    db = DatabaseManager()
                    test_transcription = {
                        'user_id': user_id,
                        'filename': 'test_recording.wav',
                        'text': 'Patient presents with acute chest pain. Blood pressure 140/90, heart rate 85.',
                        'language': 'english',
                        'medical_keywords': ['chest pain', 'blood pressure', 'heart rate'],
                        'soap_note': {
                            'subjective': 'Patient reports acute chest pain onset this morning',
                            'objective': 'Vital signs: BP 140/90, HR 85, appears anxious',
                            'assessment': 'Acute chest pain, possible cardiac etiology',
                            'plan': 'EKG, cardiac enzymes, monitor on telemetry'
                        },
                        'status': 'completed'
                    }
                    
                    trans_id = db.save_transcription(test_transcription)
                    print(f"✅ Test transcription saved: {trans_id}")
                    
                    return True
            
            return False
            
        except Exception as e:
            print(f"❌ Error creating test data: {e}")
            return False
    
    def database_stats(self):
        """Show database statistics"""
        print("\n📊 Database Statistics")
        print("-" * 40)
        
        connection = self.get_connection()
        if not connection:
            return False
        
        cursor = connection.cursor()
        
        try:
            # Count users
            cursor.execute("SELECT COUNT(*) FROM users")
            user_count = cursor.fetchone()[0]
            print(f"👥 Total Users: {user_count}")
            
            # Count active users
            cursor.execute("SELECT COUNT(*) FROM users WHERE is_active = TRUE")
            active_users = cursor.fetchone()[0]
            print(f"✅ Active Users: {active_users}")
            
            # Count transcriptions
            cursor.execute("SELECT COUNT(*) FROM transcriptions")
            trans_count = cursor.fetchone()[0]
            print(f"📝 Total Transcriptions: {trans_count}")
            
            # Count SOAP notes
            cursor.execute("SELECT COUNT(*) FROM transcriptions WHERE soap_note IS NOT NULL AND soap_note != '{}'")
            soap_count = cursor.fetchone()[0]
            print(f"🏥 SOAP Notes: {soap_count}")
            
            # Database size
            cursor.execute("""
                SELECT ROUND(SUM(data_length + index_length) / 1024 / 1024, 2) AS 'DB Size in MB'
                FROM information_schema.tables 
                WHERE table_schema = %s
            """, (self.config['database'],))
            size_result = cursor.fetchone()
            db_size = size_result[0] if size_result[0] else 0
            print(f"💾 Database Size: {db_size} MB")
            
            cursor.close()
            connection.close()
            return True
            
        except Error as e:
            print(f"❌ Error getting database stats: {e}")
            cursor.close()
            connection.close()
            return False
    
    def run_full_verification(self):
        """Run complete database verification"""
        print("🏥 CLINICAL DOCUMENTATION AI - DATABASE VERIFICATION")
        print("=" * 60)
        
        success = True
        
        # Test connection
        if not self.verify_connection():
            success = False
        
        # Verify tables
        if not self.verify_tables():
            success = False
        
        # Verify settings
        if not self.verify_settings():
            success = False
        
        # Show statistics
        if not self.database_stats():
            success = False
        
        # View data
        self.view_users()
        self.view_transcriptions()
        self.view_soap_notes()
        
        print("\n" + "=" * 60)
        if success:
            print("✅ DATABASE VERIFICATION COMPLETE - ALL CHECKS PASSED")
        else:
            print("❌ DATABASE VERIFICATION COMPLETE - SOME ISSUES FOUND")
        print("=" * 60)
        
        return success

def main():
    """Main verification function"""
    verifier = DatabaseVerifier()
    
    print("🔍 Database Verification Options:")
    print("1. Full verification")
    print("2. Create test data")
    print("3. View users only")
    print("4. View transcriptions only")
    print("5. View SOAP notes only")
    print("6. Database statistics only")
    
    try:
        choice = input("\nEnter choice (1-6) or press Enter for full verification: ").strip()
        
        if choice == "1" or choice == "":
            verifier.run_full_verification()
        elif choice == "2":
            verifier.create_test_data()
        elif choice == "3":
            verifier.view_users()
        elif choice == "4":
            verifier.view_transcriptions()
        elif choice == "5":
            verifier.view_soap_notes()
        elif choice == "6":
            verifier.database_stats()
        else:
            print("Invalid choice")
            
    except KeyboardInterrupt:
        print("\nVerification cancelled.")

if __name__ == "__main__":
    main()