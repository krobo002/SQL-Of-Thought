import mysql.connector
from decouple import config
import json

def get_mysql_connection():
    """
    Establishes a connection to the MySQL database using credentials from environment variables.
    """
    try:
        host_full = config('MYSQL_HOST')
        host_parts = host_full.split(':')
        host = host_parts[0]
        port = int(host_parts[1]) if len(host_parts) > 1 else 3306

        connection = mysql.connector.connect(
            host=host,
            port=port,
            user=config('MYSQL_USER'),
            password=config('MYSQL_PASSWORD'),
            database=config('MYSQL_DB_NAME'),
            connection_timeout=10
        )
        if connection.is_connected():
            print("Successfully connected to the database")
            return connection
    except mysql.connector.Error as e:
        print(f"Error connecting to MySQL: {e}")
        return None

def execute_query(query, params=None):
    """
    Executes a SQL query and returns the result.
    """
    connection = get_mysql_connection()
    if connection:
        cursor = connection.cursor(dictionary=True)
        try:
            cursor.execute(query, params)
            result = cursor.fetchall()
            return result
        except mysql.connector.Error as e:
            print(f"Error executing query: {e}")
            return None
        finally:
            cursor.close()
            connection.close()
    return None

def get_schema(db_name):
    """
    Retrieves the schema of the database.
    """
    connection = get_mysql_connection()
    if connection:
        cursor = connection.cursor()
        try:
            cursor.execute(f"USE {db_name}")
            cursor.execute("SHOW TABLES")
            tables = [table[0] for table in cursor.fetchall()]
            
            schema = {}
            for table_name in tables:
                if "outbox" in table_name.lower():
                    continue
                cursor.execute(f"SHOW CREATE TABLE {table_name}")
                create_table_statement = cursor.fetchone()[1]
                schema[table_name] = create_table_statement
            
            return schema
        except mysql.connector.Error as e:
            print(f"Error retrieving schema: {e}")
            return None
        finally:
            cursor.close()
            connection.close()
    return None

def main():
    # print("Attempting to connect to the database...")
    # connection = get_mysql_connection()
    # if connection:
    #     print("Connection successful. Closing connection.")
    #     connection.close()
    # else:
    #     print("Connection failed.")

    # query = "SELECT * FROM reference_asset limit 10;"
    # res = execute_query(query=query)
    # print(res)

    db_name = "row_store$integration$content"
    db_schema = get_schema(db_name=db_name)
    with open(f"{db_name}.json", "w") as f:
        json.dump(db_schema, f, indent=4)
    print("Database schema saved to db_schema.json")
    print(db_schema)

    # db = "row_store$integration$content"
    # res = get_schema(db)
    # print(res)

if __name__ == '__main__':
    main()
