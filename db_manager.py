"""
Database manager for MySQL integration
"""

import mysql.connector
from mysql.connector import Error
import json
import uuid
from datetime import datetime
from typing import Dict, List, Optional
import os
from pathlib import Path

class DatabaseManager:
    """Handles MySQL database operations"""
    
    def __init__(self, config_file: str = "db_config.json"):
        self.config_file = config_file
        self.connection = None
        self.config = self.load_config()
        self.init_database()
    
    def load_config(self) -> Dict:
        """Load database configuration"""
        default_config = {
            "host": "localhost",
            "port": 3306,
            "user": "clinical_user",
            "password": "clinical_password",
            "database": "clinical_docs"
        }
        
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                    return {**default_config, **config}
            except Exception as e:
                print(f"Error loading config file: {e}")
        
        # Save default config for future use
        try:
            with open(self.config_file, 'w') as f:
                json.dump(default_config, f, indent=2)
        except Exception as e:
            print(f"Error saving config file: {e}")
        
        return default_config
    
    def get_connection(self):
        """Get database connection"""
        try:
            if self.connection is None or not self.connection.is_connected():
                self.connection = mysql.connector.connect(
                    host=self.config['host'],
                    port=self.config['port'],
                    user=self.config['user'],
                    password=self.config['password'],
                    database=self.config['database'],
                    autocommit=True
                )
            return self.connection
        except Error as e:
            print(f"Error connecting to MySQL: {e}")
            return None
    
    def init_database(self):
        """Initialize the MySQL database and tables"""
        try:
            # First, try to connect without database to create it
            temp_connection = mysql.connector.connect(
                host=self.config['host'],
                port=self.config['port'],
                user=self.config['user'],
                password=self.config['password'],
                autocommit=True
            )
            
            cursor = temp_connection.cursor()
            
            # Create database if it doesn't exist
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS {self.config['database']}")
            cursor.execute(f"USE {self.config['database']}")
            
            # Create users table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id VARCHAR(36) PRIMARY KEY,
                    username VARCHAR(255) UNIQUE NOT NULL,
                    password_hash VARCHAR(255) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_active BOOLEAN DEFAULT TRUE
                )
            """)
            
            # Create transcriptions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS transcriptions (
                    id VARCHAR(36) PRIMARY KEY,
                    user_id VARCHAR(36) NOT NULL,
                    filename VARCHAR(255) NOT NULL,
                    transcription_text TEXT,
                    language VARCHAR(50),
                    medical_keywords JSON,
                    soap_note JSON,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    status VARCHAR(50) DEFAULT 'completed',
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
            """)
            
            # Create app_settings table for remote activation
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS app_settings (
                    id VARCHAR(36) PRIMARY KEY,
                    setting_key VARCHAR(255) UNIQUE NOT NULL,
                    setting_value TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                )
            """)
            
            # Insert default activation setting
            cursor.execute("""
                INSERT IGNORE INTO app_settings (id, setting_key, setting_value) 
                VALUES (%s, 'app_active', 'true')
            """, (str(uuid.uuid4()),))
            
            # Insert default API key
            cursor.execute("""
                INSERT IGNORE INTO app_settings (id, setting_key, setting_value) 
                VALUES (%s, 'api_key', 'clinical_api_key_2025')
            """, (str(uuid.uuid4()),))
            
            cursor.close()
            temp_connection.close()
            
            print("✅ Database initialized successfully")
            
        except Error as e:
            print(f"❌ Error initializing database: {e}")
            raise
    
    def save_transcription(self, transcription_data: Dict) -> str:
        """Save transcription to database"""
        connection = self.get_connection()
        if not connection:
            raise Exception("Database connection failed")
        
        transcription_id = str(uuid.uuid4())
        cursor = connection.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO transcriptions 
                (id, user_id, filename, transcription_text, language, medical_keywords, soap_note, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                transcription_id,
                transcription_data.get('user_id'),
                transcription_data.get('filename', ''),
                transcription_data.get('text', ''),
                transcription_data.get('language', 'unknown'),
                json.dumps(transcription_data.get('medical_keywords', [])),
                json.dumps(transcription_data.get('soap_note', {})),
                transcription_data.get('status', 'completed')
            ))
            
            cursor.close()
            return transcription_id
            
        except Error as e:
            cursor.close()
            raise Exception(f"Error saving transcription: {e}")
    
    def get_transcriptions(self, user_id: str, limit: int = 10) -> List[Dict]:
        """Get recent transcriptions for a user"""
        connection = self.get_connection()
        if not connection:
            return []
        
        cursor = connection.cursor()
        
        try:
            cursor.execute("""
                SELECT id, filename, transcription_text, created_at, status
                FROM transcriptions 
                WHERE user_id = %s
                ORDER BY created_at DESC 
                LIMIT %s
            """, (user_id, limit))
            
            results = []
            for row in cursor.fetchall():
                results.append({
                    'id': row[0],
                    'filename': row[1],
                    'text': row[2][:100] + '...' if len(row[2]) > 100 else row[2],
                    'created_at': row[3],
                    'status': row[4]
                })
            
            cursor.close()
            return results
            
        except Error as e:
            cursor.close()
            print(f"Error getting transcriptions: {e}")
            return []
    
    def get_transcription_by_id(self, transcription_id: str) -> Optional[Dict]:
        """Get specific transcription by ID"""
        connection = self.get_connection()
        if not connection:
            return None
        
        cursor = connection.cursor()
        
        try:
            cursor.execute("""
                SELECT id, user_id, filename, transcription_text, language, 
                       medical_keywords, soap_note, created_at, status
                FROM transcriptions 
                WHERE id = %s
            """, (transcription_id,))
            
            row = cursor.fetchone()
            if row:
                result = {
                    'id': row[0],
                    'user_id': row[1],
                    'filename': row[2],
                    'text': row[3],
                    'language': row[4],
                    'medical_keywords': json.loads(row[5]) if row[5] else [],
                    'soap_note': json.loads(row[6]) if row[6] else {},
                    'created_at': row[7],
                    'status': row[8]
                }
                cursor.close()
                return result
            
            cursor.close()
            return None
            
        except Error as e:
            cursor.close()
            print(f"Error getting transcription: {e}")
            return None
    
    def get_setting(self, key: str) -> Optional[str]:
        """Get application setting"""
        connection = self.get_connection()
        if not connection:
            return None
        
        cursor = connection.cursor()
        
        try:
            cursor.execute("""
                SELECT setting_value FROM app_settings WHERE setting_key = %s
            """, (key,))
            
            row = cursor.fetchone()
            cursor.close()
            return row[0] if row else None
            
        except Error as e:
            cursor.close()
            print(f"Error getting setting: {e}")
            return None
    
    def update_setting(self, key: str, value: str) -> bool:
        """Update application setting"""
        connection = self.get_connection()
        if not connection:
            return False
        
        cursor = connection.cursor()
        
        try:
            cursor.execute("""
                UPDATE app_settings SET setting_value = %s WHERE setting_key = %s
            """, (value, key))
            
            cursor.close()
            return True
            
        except Error as e:
            cursor.close()
            print(f"Error updating setting: {e}")
            return False
    
    def close(self):
        """Close database connection"""
        if self.connection and self.connection.is_connected():
            self.connection.close()