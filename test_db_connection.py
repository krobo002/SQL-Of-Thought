#!/usr/bin/env python3
"""
Simple test script to verify database connection and query functionality
using the credentials from .env file
"""

import sys
import os

# Add the src directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from database.mysql_connection import get_mysql_connection, execute_query

def test_connection():
    """Test the database connection"""
    print("Testing database connection...")
    
    connection = get_mysql_connection()
    if connection:
        print("✅ Database connection successful!")
        connection.close()
        return True
    else:
        print("❌ Database connection failed!")
        return False

def test_simple_query():
    """Test executing a simple query"""
    print("\nTesting simple query...")
    
    # Get a count of tables in the database
    query = "SELECT COUNT(*) as table_count FROM information_schema.tables WHERE table_schema = %s"
    params = ('row_store$integration$content',)
    
    result = execute_query(query, params)
    if result:
        table_count = result[0]['table_count']
        print(f"✅ Query successful! Found {table_count} tables in the database.")
        return True
    else:
        print("❌ Query failed!")
        return False

def test_sample_data_query():
    """Test querying actual data from a table"""
    import re
    
    print("\nTesting sample data query...")
    
    # First, let's get a list of tables
    query = "SHOW TABLES"
    result = execute_query(query)
    
    if result and len(result) > 0:
        # Get the first table name
        first_table = list(result[0].values())[0]
        print(f"Sample table found: {first_table}")
        
        # Validate table name contains only safe characters (alphanumeric, underscore, dollar sign)
        if not re.match(r'^[a-zA-Z0-9_$]+$', first_table):
            print("❌ Table name contains unsafe characters, skipping sample query")
            return False
        
        # Query a few rows from the first table using validated identifier
        sample_query = f"SELECT * FROM `{first_table}` LIMIT 3"
        sample_result = execute_query(sample_query)
        
        if sample_result is not None:
            print(f"✅ Sample data query successful! Found {len(sample_result)} rows.")
            if len(sample_result) > 0:
                print("Sample columns:", list(sample_result[0].keys())[:5])  # Show first 5 columns
            return True
        else:
            print("❌ Sample data query failed!")
            return False
    else:
        print("❌ Could not retrieve table list!")
        return False

def main():
    """Main test function"""
    print("=" * 50)
    print("MySQL Database Connection Test")
    print("=" * 50)
    
    # Test connection
    connection_success = test_connection()
    
    if connection_success:
        # Test simple query
        query_success = test_simple_query()
        
        if query_success:
            # Test sample data query
            data_success = test_sample_data_query()
            
            if data_success:
                print("\n" + "=" * 50)
                print("🎉 All tests passed! Database is ready to use.")
                print("=" * 50)
                return True
    
    print("\n" + "=" * 50)
    print("❌ Some tests failed. Please check your configuration.")
    print("=" * 50)
    return False

if __name__ == "__main__":
    main()