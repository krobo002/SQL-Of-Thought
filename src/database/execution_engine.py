"""
Database Execution Engine for SQL-of-Thought Framework

This module provides database execution functionality to run generated SQL queries
and compare results for the SQL-of-Thought pipeline.
"""

import sqlite3
import mysql.connector
import time
import logging
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ExecutionResult:
    """Result from SQL execution"""
    success: bool
    data: Optional[List[Dict]] = None
    row_count: int = 0
    execution_time: float = 0.0
    error_message: Optional[str] = None
    sql_executed: Optional[str] = None


class DatabaseExecutor:
    """
    Base class for database execution engines.
    
    This class provides the interface for executing SQL queries and comparing results
    for the SQL-of-Thought framework's evaluation and correction loop.
    """
    
    def __init__(self, connection_config: Dict):
        """
        Initialize the database executor.
        
        Args:
            connection_config: Database connection configuration
        """
        self.connection_config = connection_config
        self.logger = logging.getLogger(__name__)
    
    def execute(self, sql: str, fetch_results: bool = True) -> ExecutionResult:
        """
        Execute SQL query and return results.
        
        Args:
            sql: SQL query to execute
            fetch_results: Whether to fetch and return results
            
        Returns:
            ExecutionResult containing query results or error information
        """
        raise NotImplementedError("Subclasses must implement execute method")
    
    def compare_results(self, result1: ExecutionResult, result2: ExecutionResult) -> Dict:
        """
        Compare two execution results.
        
        Args:
            result1: First execution result
            result2: Second execution result (ground truth)
            
        Returns:
            Dictionary containing comparison results
        """
        if not result1.success or not result2.success:
            return {
                "match": False,
                "reason": "One or both queries failed to execute",
                "result1_success": result1.success,
                "result2_success": result2.success,
                "result1_error": result1.error_message,
                "result2_error": result2.error_message
            }
        
        # Compare row counts
        if result1.row_count != result2.row_count:
            return {
                "match": False,
                "reason": f"Row count mismatch: {result1.row_count} vs {result2.row_count}",
                "result1_count": result1.row_count,
                "result2_count": result2.row_count
            }
        
        # Compare actual data if available
        if result1.data is not None and result2.data is not None:
            # Sort both result sets for comparison (order might differ)
            sorted_data1 = self._sort_result_data(result1.data)
            sorted_data2 = self._sort_result_data(result2.data)
            
            if sorted_data1 == sorted_data2:
                return {
                    "match": True,
                    "reason": "Results match exactly",
                    "row_count": result1.row_count
                }
            else:
                return {
                    "match": False,
                    "reason": "Data content mismatch",
                    "sample_diff": self._get_sample_diff(sorted_data1, sorted_data2)
                }
        
        # If we can't compare data, just check row counts
        return {
            "match": result1.row_count == result2.row_count,
            "reason": f"Row count comparison only: {result1.row_count} vs {result2.row_count}",
            "row_count_match": result1.row_count == result2.row_count
        }
    
    def _sort_result_data(self, data: List[Dict]) -> List[Dict]:
        """Sort result data for consistent comparison"""
        if not data:
            return data
        
        try:
            # Convert all values to strings for sorting
            return sorted(data, key=lambda x: str(sorted(x.items())))
        except Exception:
            # If sorting fails, return original data
            return data
    
    def _get_sample_diff(self, data1: List[Dict], data2: List[Dict]) -> Dict:
        """Get a sample of differences between two result sets"""
        diff = {
            "first_few_rows_data1": data1[:3] if data1 else [],
            "first_few_rows_data2": data2[:3] if data2 else [],
            "data1_length": len(data1),
            "data2_length": len(data2)
        }
        return diff


class SQLiteExecutor(DatabaseExecutor):
    """
    SQLite database executor for the SQL-of-Thought framework.
    
    This executor is specifically designed for Spider dataset evaluation
    which uses SQLite databases.
    """
    
    def __init__(self, db_path: str):
        """
        Initialize SQLite executor.
        
        Args:
            db_path: Path to SQLite database file
        """
        super().__init__({"db_path": db_path})
        self.db_path = Path(db_path)
        
        if not self.db_path.exists():
            raise FileNotFoundError(f"SQLite database not found: {db_path}")
    
    def execute(self, sql: str, fetch_results: bool = True) -> ExecutionResult:
        """
        Execute SQL query on SQLite database.
        
        Args:
            sql: SQL query to execute
            fetch_results: Whether to fetch and return results
            
        Returns:
            ExecutionResult containing query results or error information
        """
        start_time = time.time()
        
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                # Set row factory to return dictionaries
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                # Execute the query
                cursor.execute(sql)
                
                if fetch_results:
                    # Fetch all results and convert to list of dictionaries
                    rows = cursor.fetchall()
                    data = [dict(row) for row in rows]
                    row_count = len(data)
                else:
                    data = None
                    row_count = cursor.rowcount if cursor.rowcount >= 0 else 0
                
                execution_time = time.time() - start_time
                
                return ExecutionResult(
                    success=True,
                    data=data,
                    row_count=row_count,
                    execution_time=execution_time,
                    sql_executed=sql
                )
                
        except sqlite3.Error as e:
            execution_time = time.time() - start_time
            error_message = f"SQLite error: {str(e)}"
            self.logger.error(f"SQL execution failed: {error_message}")
            
            return ExecutionResult(
                success=False,
                execution_time=execution_time,
                error_message=error_message,
                sql_executed=sql
            )
        
        except Exception as e:
            execution_time = time.time() - start_time
            error_message = f"Unexpected error: {str(e)}"
            self.logger.error(f"SQL execution failed: {error_message}")
            
            return ExecutionResult(
                success=False,
                execution_time=execution_time,
                error_message=error_message,
                sql_executed=sql
            )
    
    def get_schema_info(self) -> Dict:
        """Get schema information from the SQLite database"""
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                cursor = conn.cursor()
                
                # Get all tables
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
                tables = [row[0] for row in cursor.fetchall()]
                
                schema_info = {"tables": []}
                
                for table_name in tables:
                    # Get column information for each table
                    cursor.execute(f"PRAGMA table_info({table_name});")
                    columns = cursor.fetchall()
                    
                    table_info = {
                        "name": table_name,
                        "columns": []
                    }
                    
                    for col in columns:
                        column_info = {
                            "name": col[1],
                            "type": col[2],
                            "nullable": not col[3],
                            "primary_key": bool(col[5])
                        }
                        table_info["columns"].append(column_info)
                    
                    # Get foreign key information
                    cursor.execute(f"PRAGMA foreign_key_list({table_name});")
                    foreign_keys = cursor.fetchall()
                    
                    table_info["foreign_keys"] = []
                    for fk in foreign_keys:
                        fk_info = {
                            "column": fk[3],
                            "referenced_table": fk[2],
                            "referenced_column": fk[4]
                        }
                        table_info["foreign_keys"].append(fk_info)
                    
                    schema_info["tables"].append(table_info)
                
                return schema_info
                
        except Exception as e:
            self.logger.error(f"Failed to get schema info: {str(e)}")
            return {"tables": [], "error": str(e)}


class MySQLExecutor(DatabaseExecutor):
    """
    MySQL database executor for the SQL-of-Thought framework.
    """
    
    def __init__(self, host: str, user: str, password: str, database: str, port: int = 3306):
        """
        Initialize MySQL executor.
        
        Args:
            host: MySQL server host
            user: Database user
            password: Database password
            database: Database name
            port: MySQL server port
        """
        connection_config = {
            "host": host,
            "user": user,
            "password": password,
            "database": database,
            "port": port
        }
        super().__init__(connection_config)
    
    def execute(self, sql: str, fetch_results: bool = True) -> ExecutionResult:
        """
        Execute SQL query on MySQL database.
        
        Args:
            sql: SQL query to execute
            fetch_results: Whether to fetch and return results
            
        Returns:
            ExecutionResult containing query results or error information
        """
        start_time = time.time()
        
        try:
            with mysql.connector.connect(**self.connection_config) as conn:
                cursor = conn.cursor(dictionary=True)
                
                # Execute the query
                cursor.execute(sql)
                
                if fetch_results and cursor.with_rows:
                    # Fetch all results
                    data = cursor.fetchall()
                    row_count = len(data)
                else:
                    data = None
                    row_count = cursor.rowcount if cursor.rowcount >= 0 else 0
                
                execution_time = time.time() - start_time
                
                return ExecutionResult(
                    success=True,
                    data=data,
                    row_count=row_count,
                    execution_time=execution_time,
                    sql_executed=sql
                )
                
        except mysql.connector.Error as e:
            execution_time = time.time() - start_time
            error_message = f"MySQL error: {str(e)}"
            self.logger.error(f"SQL execution failed: {error_message}")
            
            return ExecutionResult(
                success=False,
                execution_time=execution_time,
                error_message=error_message,
                sql_executed=sql
            )
        
        except Exception as e:
            execution_time = time.time() - start_time
            error_message = f"Unexpected error: {str(e)}"
            self.logger.error(f"SQL execution failed: {error_message}")
            
            return ExecutionResult(
                success=False,
                execution_time=execution_time,
                error_message=error_message,
                sql_executed=sql
            )


class DatabaseExecutorFactory:
    """Factory for creating database executors"""
    
    @staticmethod
    def create_executor(db_type: str, **kwargs) -> DatabaseExecutor:
        """
        Create a database executor based on type.
        
        Args:
            db_type: Type of database ('sqlite', 'mysql')
            **kwargs: Database connection parameters
            
        Returns:
            DatabaseExecutor instance
        """
        if db_type.lower() == 'sqlite':
            if 'db_path' not in kwargs:
                raise ValueError("SQLite executor requires 'db_path' parameter")
            return SQLiteExecutor(kwargs['db_path'])
        
        elif db_type.lower() == 'mysql':
            required_params = ['host', 'user', 'password', 'database']
            for param in required_params:
                if param not in kwargs:
                    raise ValueError(f"MySQL executor requires '{param}' parameter")
            
            return MySQLExecutor(
                host=kwargs['host'],
                user=kwargs['user'],
                password=kwargs['password'],
                database=kwargs['database'],
                port=kwargs.get('port', 3306)
            )
        
        else:
            raise ValueError(f"Unsupported database type: {db_type}")


# Convenience function for Spider dataset evaluation
def create_spider_executor(database_path: str) -> SQLiteExecutor:
    """
    Create a SQLite executor for Spider dataset evaluation.
    
    Args:
        database_path: Path to the Spider SQLite database
        
    Returns:
        SQLiteExecutor configured for the Spider database
    """
    return SQLiteExecutor(database_path)