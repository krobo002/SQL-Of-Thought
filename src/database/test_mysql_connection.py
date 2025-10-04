import unittest
from unittest.mock import patch, MagicMock
import mysql.connector
from src.database.mysql_connection import get_mysql_connection, execute_query, get_schema

class TestMysqlConnection(unittest.TestCase):

    @patch('src.database.mysql_connection.config')
    @patch('src.database.mysql_connection.mysql.connector.connect')
    def test_get_mysql_connection_success(self, mock_connect, mock_config):
        # Arrange
        mock_config.side_effect = lambda key: {
            'MYSQL_HOST': 'localhost',
            'MYSQL_USER': 'user',
            'MYSQL_PASSWORD': 'password',
            'MYSQL_DB_NAME': 'test_db'
        }[key]
        
        mock_connection = MagicMock()
        mock_connection.is_connected.return_value = True
        mock_connect.return_value = mock_connection

        # Act
        connection = get_mysql_connection()

        # Assert
        self.assertIsNotNone(connection)
        mock_connect.assert_called_once_with(
            host='localhost',
            user='user',
            password='password',
            database='test_db'
        )
        self.assertEqual(connection, mock_connection)

    @patch('src.database.mysql_connection.config')
    @patch('src.database.mysql_connection.mysql.connector.connect')
    def test_get_mysql_connection_failure(self, mock_connect, mock_config):
        # Arrange
        mock_config.side_effect = lambda key: {
            'MYSQL_HOST': 'localhost',
            'MYSQL_USER': 'user',
            'MYSQL_PASSWORD': 'password',
            'MYSQL_DB_NAME': 'test_db'
        }[key]
        
        mock_connect.side_effect = mysql.connector.Error("Connection failed")

        # Act
        connection = get_mysql_connection()

        # Assert
        self.assertIsNone(connection)

    @patch('src.database.mysql_connection.get_mysql_connection')
    def test_execute_query_success(self, mock_get_connection):
        # Arrange
        mock_connection = MagicMock()
        mock_cursor = MagicMock()
        mock_connection.cursor.return_value = mock_cursor
        mock_get_connection.return_value = mock_connection
        
        expected_result = [{'id': 1, 'name': 'test'}]
        mock_cursor.fetchall.return_value = expected_result
        
        query = "SELECT * FROM test_table"
        
        # Act
        result = execute_query(query)
        
        # Assert
        self.assertEqual(result, expected_result)
        mock_get_connection.assert_called_once()
        mock_connection.cursor.assert_called_once_with(dictionary=True)
        mock_cursor.execute.assert_called_once_with(query, None)
        mock_cursor.fetchall.assert_called_once()
        mock_cursor.close.assert_called_once()
        mock_connection.close.assert_called_once()

    @patch('src.database.mysql_connection.get_mysql_connection')
    def test_execute_query_no_connection(self, mock_get_connection):
        # Arrange
        mock_get_connection.return_value = None
        
        # Act
        result = execute_query("SELECT * FROM test_table")
        
        # Assert
        self.assertIsNone(result)

    @patch('src.database.mysql_connection.get_mysql_connection')
    def test_execute_query_error(self, mock_get_connection):
        # Arrange
        mock_connection = MagicMock()
        mock_cursor = MagicMock()
        mock_connection.cursor.return_value = mock_cursor
        mock_get_connection.return_value = mock_connection
        
        mock_cursor.execute.side_effect = mysql.connector.Error("Query failed")
        
        # Act
        result = execute_query("SELECT * FROM test_table")
        
        # Assert
        self.assertIsNone(result)
        mock_cursor.close.assert_called_once()
        mock_connection.close.assert_called_once()

    @patch('src.database.mysql_connection.get_mysql_connection')
    def test_get_schema_success(self, mock_get_connection):
        # Arrange
        mock_connection = MagicMock()
        mock_cursor = MagicMock()
        mock_connection.cursor.return_value = mock_cursor
        mock_get_connection.return_value = mock_connection
        
        mock_cursor.fetchall.side_effect = [
            [('table1',), ('table2',)],  # SHOW TABLES
        ]
        mock_cursor.fetchone.side_effect = [
            (None, 'CREATE TABLE table1...'),
            (None, 'CREATE TABLE table2...')
        ]
        
        db_name = "test_db"
        
        # Act
        schema = get_schema(db_name)
        
        # Assert
        self.assertIsNotNone(schema)
        self.assertIn('table1', schema)
        self.assertIn('table2', schema)
        self.assertEqual(schema['table1'], 'CREATE TABLE table1...')
        self.assertEqual(schema['table2'], 'CREATE TABLE table2...')
        
        mock_cursor.execute.assert_any_call(f"USE {db_name}")
        mock_cursor.execute.assert_any_call("SHOW TABLES")
        mock_cursor.execute.assert_any_call("SHOW CREATE TABLE table1")
        mock_cursor.execute.assert_any_call("SHOW CREATE TABLE table2")
        mock_cursor.close.assert_called_once()
        mock_connection.close.assert_called_once()

    @patch('src.database.mysql_connection.get_mysql_connection')
    def test_get_schema_no_connection(self, mock_get_connection):
        # Arrange
        mock_get_connection.return_value = None
        
        # Act
        schema = get_schema("test_db")
        
        # Assert
        self.assertIsNone(schema)

    @patch('src.database.mysql_connection.get_mysql_connection')
    def test_get_schema_error(self, mock_get_connection):
        # Arrange
        mock_connection = MagicMock()
        mock_cursor = MagicMock()
        mock_connection.cursor.return_value = mock_cursor
        mock_get_connection.return_value = mock_connection
        
        mock_cursor.execute.side_effect = mysql.connector.Error("Schema retrieval failed")
        
        # Act
        schema = get_schema("test_db")
        
        # Assert
        self.assertIsNone(schema)
        mock_cursor.close.assert_called_once()
        mock_connection.close.assert_called_once()

if __name__ == '__main__':
    unittest.main()
