"""
MySQL setup script for the clinical documentation application
"""

import mysql.connector
from mysql.connector import Error
import getpass
import json
import os

def create_mysql_user_and_database():
    """Setup MySQL database and user for the application"""
    
    print("🏥 Clinical Documentation MySQL Setup")
    print("=====================================")
    
    # Get MySQL root credentials
    print("\n📋 MySQL Root Credentials:")
    root_user = input("MySQL root username (default: root): ").strip() or "root"
    root_password = getpass.getpass("MySQL root password: ")
    host = input("MySQL host (default: localhost): ").strip() or "localhost"
    port = input("MySQL port (default: 3306): ").strip() or "3306"
    
    try:
        port = int(port)
    except ValueError:
        print("❌ Invalid port number. Using default 3306.")
        port = 3306
    
    # Database configuration
    db_config = {
        "host": host,
        "port": port,
        "user": "clinical_user",
        "password": "clinical_password",
        "database": "clinical_docs"
    }
    
    print(f"\n🔧 Setting up database: {db_config['database']}")
    print(f"📊 Creating user: {db_config['user']}")
    
    try:
        # Connect to MySQL as root
        connection = mysql.connector.connect(
            host=host,
            port=port,
            user=root_user,
            password=root_password
        )
        
        cursor = connection.cursor()
        
        # Create database
        print("📁 Creating database...")
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {db_config['database']}")
        
        # Create user
        print("👤 Creating user...")
        cursor.execute(f"CREATE USER IF NOT EXISTS '{db_config['user']}'@'{host}' IDENTIFIED BY '{db_config['password']}'")
        cursor.execute(f"CREATE USER IF NOT EXISTS '{db_config['user']}'@'localhost' IDENTIFIED BY '{db_config['password']}'")
        
        # Grant privileges
        print("🔐 Granting privileges...")
        cursor.execute(f"GRANT ALL PRIVILEGES ON {db_config['database']}.* TO '{db_config['user']}'@'{host}'")
        cursor.execute(f"GRANT ALL PRIVILEGES ON {db_config['database']}.* TO '{db_config['user']}'@'localhost'")
        cursor.execute("FLUSH PRIVILEGES")
        
        cursor.close()
        connection.close()
        
        print("✅ MySQL setup completed successfully!")
        
        # Save configuration
        config_file = "db_config.json"
        with open(config_file, 'w') as f:
            json.dump(db_config, f, indent=2)
        
        print(f"💾 Database configuration saved to {config_file}")
        
        # Test connection
        print("\n🔍 Testing database connection...")
        test_connection = mysql.connector.connect(**db_config)
        if test_connection.is_connected():
            print("✅ Database connection test successful!")
            
            # Initialize tables
            print("🏗️ Initializing database tables...")
            from db_manager import DatabaseManager
            db_manager = DatabaseManager(config_file)
            print("✅ Database tables initialized!")
            
            test_connection.close()
        else:
            print("❌ Database connection test failed!")
        
        return True
        
    except Error as e:
        print(f"❌ MySQL setup error: {e}")
        return False
    except Exception as e:
        print(f"❌ Setup error: {e}")
        return False

def install_mysql_instructions():
    """Display MySQL installation instructions"""
    print("\n📦 MySQL Installation Instructions")
    print("==================================")
    print("If MySQL is not installed, please install it first:")
    print()
    print("🪟 Windows:")
    print("   1. Download MySQL Installer from https://dev.mysql.com/downloads/installer/")
    print("   2. Run the installer and select 'MySQL Server'")
    print("   3. Follow the installation wizard")
    print("   4. Set a root password")
    print()
    print("🐧 Linux (Ubuntu/Debian):")
    print("   sudo apt update")
    print("   sudo apt install mysql-server")
    print("   sudo mysql_secure_installation")
    print()
    print("🍎 macOS:")
    print("   brew install mysql")
    print("   brew services start mysql")
    print("   mysql_secure_installation")
    print()

def check_mysql_installation():
    """Check if MySQL is installed and running"""
    try:
        # Try to connect to MySQL
        connection = mysql.connector.connect(
            host='localhost',
            user='root',
            password='',  # Empty password for basic check
            connect_timeout=5
        )
        connection.close()
        return True
    except Error as e:
        if "Access denied" in str(e):
            # MySQL is installed but needs proper credentials
            return True
        return False
    except Exception:
        return False

if __name__ == "__main__":
    print("🏥 Clinical Documentation MySQL Setup")
    print("=====================================")
    
    if not check_mysql_installation():
        print("❌ MySQL is not installed or not running.")
        install_mysql_instructions()
        
        choice = input("\nDo you want to continue with the setup anyway? (y/n): ").strip().lower()
        if choice != 'y':
            print("Setup cancelled.")
            exit()
    
    if create_mysql_user_and_database():
        print("\n🎉 MySQL setup completed successfully!")
        print("You can now run the clinical documentation application.")
        print("\nTo start the application, run:")
        print("   python clinical_app.py")
        print("\nTo start the activation service, run:")
        print("   python activation_service.py")
    else:
        print("\n❌ MySQL setup failed!")
        print("Please check the error messages above and try again.")