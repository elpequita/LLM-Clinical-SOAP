"""
Database manager for MySQL integration
"""

import mysql.connector
from mysql.connector import Error
import json
import re
import uuid
import threading
from datetime import datetime
from typing import Dict, List, Optional
import os
from pathlib import Path

# MySQL identifiers (database names) cannot be parameterized in DDL, so they
# are interpolated into f-strings. Reject anything that isn't a plain identifier
# to close the SQL-injection surface that opens up if db_config.json is tampered.
_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9_]+$")

# Tracks databases whose schema has already been initialized in this process.
# clinical_app.py, auth_manager, and security_manager each construct a
# DatabaseManager at startup; without this guard each one would re-run the
# full DDL block. IF NOT EXISTS makes that idempotent but it's still wasted
# round-trips.
_initialized_dbs: set = set()


class DatabaseManager:
    """Handles MySQL database operations"""

    def __init__(self, config_file: str = "db_config.json"):
        self.config_file = config_file
        # Per-thread connection storage. Each thread gets its own MySQL
        # connection lazily on first use. Avoids the prior single-shared-
        # connection design that wasn't safe for the worker threads
        # introduced in clinical_app.py.
        self._local = threading.local()
        self.config = self.load_config()
        if self.config["database"] not in _initialized_dbs:
            self.init_database()
            _initialized_dbs.add(self.config["database"])
    
    def load_config(self) -> Dict:
        """Load database configuration.

        Resolution order: defaults → db_config.json → environment variables.
        Environment variables (CLINICAL_DB_*) win, so credentials can be kept
        out of the on-disk JSON file in production deployments.
        """
        default_config = {
            "host": "localhost",
            "port": 3306,
            "user": "clinical_user",
            "password": "clinical_password",
            "database": "clinical_docs"
        }

        config = dict(default_config)

        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    config.update(json.load(f))
            except Exception as e:
                print(f"Error loading config file: {e}")

        # Env-var overrides — these take precedence over the JSON file so an
        # operator can keep secrets out of disk artifacts.
        env_overrides = {
            "host": os.environ.get("CLINICAL_DB_HOST"),
            "user": os.environ.get("CLINICAL_DB_USER"),
            "password": os.environ.get("CLINICAL_DB_PASSWORD"),
            "database": os.environ.get("CLINICAL_DB_NAME"),
        }
        for k, v in env_overrides.items():
            if v:
                config[k] = v
        port_env = os.environ.get("CLINICAL_DB_PORT")
        if port_env:
            try:
                config["port"] = int(port_env)
            except ValueError:
                print(f"Invalid CLINICAL_DB_PORT={port_env!r}, ignoring")

        # Validate the database name early — it's interpolated into DDL and
        # must therefore be a strict identifier (alnum + underscore).
        if not _IDENTIFIER_RE.match(config["database"]):
            raise ValueError(
                f"Invalid database name {config['database']!r}: "
                "must be alphanumeric or underscore only."
            )

        return config

    def get_connection(self):
        """Get the connection for the current thread (created lazily)."""
        try:
            conn = getattr(self._local, "connection", None)
            if conn is None or not conn.is_connected():
                self._local.connection = mysql.connector.connect(
                    host=self.config['host'],
                    port=self.config['port'],
                    user=self.config['user'],
                    password=self.config['password'],
                    database=self.config['database'],
                    autocommit=True,
                )
            return self._local.connection
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
            
            # Seed API key from env (CLINICAL_API_KEY) — first value if comma-separated.
            # If not set, leave the row absent so security_manager fails closed instead
            # of authenticating with a hardcoded key.
            seed_key_raw = os.environ.get("CLINICAL_API_KEY", "").strip()
            seed_key = seed_key_raw.split(",", 1)[0].strip() if seed_key_raw else ""
            if seed_key:
                cursor.execute(
                    """
                    INSERT IGNORE INTO app_settings (id, setting_key, setting_value)
                    VALUES (%s, 'api_key', %s)
                    """,
                    (str(uuid.uuid4()), seed_key),
                )
            else:
                print(
                    "WARNING: CLINICAL_API_KEY not set; api_key row was not seeded. "
                    "Activation calls will fail until you set the env var and re-seed."
                )
            
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
                    'text': (row[2] or "")[:100] + ('...' if row[2] and len(row[2]) > 100 else ''),
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
        """Close the calling thread's connection (if any)."""
        conn = getattr(self._local, "connection", None)
        if conn is not None and conn.is_connected():
            conn.close()
            self._local.connection = None