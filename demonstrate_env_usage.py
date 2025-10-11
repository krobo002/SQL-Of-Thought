#!/usr/bin/env python3
"""
Demonstration script showing the database connection using credentials from .env file
"""

import sys
import os
from decouple import config

# Add the src directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from database.mysql_connection import get_mysql_connection, execute_query

def demonstrate_env_usage():
    """Demonstrate that database connection uses .env file credentials"""
    print("=" * 60)
    print("DATABASE CONNECTION USING .ENV FILE CREDENTIALS")
    print("=" * 60)
    
    # Show the environment variables being used (without exposing sensitive data)
    print("Reading database configuration from .env file:")
    print(f"📍 MYSQL_HOST: {config('MYSQL_HOST')}")
    print(f"👤 MYSQL_USER: {config('MYSQL_USER')}")
    print(f"🔒 MYSQL_PASSWORD: {'*' * len(config('MYSQL_PASSWORD'))}")  # Mask password
    print(f"🗄️  MYSQL_DB_NAME: {config('MYSQL_DB_NAME')}")
    print()
    
    # Test the connection
    print("Testing connection with these credentials...")
    connection = get_mysql_connection()
    
    if connection:
        print("✅ Successfully connected to MySQL database!")
        
        # Get database info to confirm we're connected to the right database
        query = "SELECT DATABASE() as current_db, USER() as current_user_info, VERSION() as mysql_version"
        result = execute_query(query)
        
        if result:
            db_info = result[0]
            print(f"✅ Connected to database: {db_info['current_db']}")
            print(f"✅ Connected as user: {db_info['current_user_info']}")
            print(f"✅ MySQL version: {db_info['mysql_version']}")
            
            # Show table count to confirm we have access
            count_query = "SELECT COUNT(*) as table_count FROM information_schema.tables WHERE table_schema = DATABASE()"
            count_result = execute_query(count_query)
            if count_result:
                table_count = count_result[0]['table_count']
                print(f"✅ Database contains {table_count} tables")
        
        connection.close()
        print("\n🎉 Database is successfully configured using .env file credentials!")
        return True
    else:
        print("❌ Failed to connect to database with .env credentials")
        return False

def show_env_file_contents():
    """Show relevant parts of the .env file (masking sensitive data)"""
    print("\n" + "=" * 60)
    print("CURRENT .ENV FILE CONFIGURATION")
    print("=" * 60)
    
    env_file_path = ".env"
    if os.path.exists(env_file_path):
        print("📄 Reading from .env file:")
        with open(env_file_path, 'r') as f:
            lines = f.readlines()
            
        for line in lines:
            line = line.strip()
            if line.startswith('MYSQL_'):
                if 'PASSWORD' in line:
                    # Mask the password
                    key, value = line.split('=', 1)
                    masked_value = '*' * len(value.strip('"'))
                    print(f"   {key}=\"{masked_value}\"")
                else:
                    print(f"   {line}")
    else:
        print("❌ .env file not found!")

if __name__ == "__main__":
    show_env_file_contents()
    demonstrate_env_usage()