"""
Error Taxonomy for SQL-of-Thought Framework

This module implements the comprehensive error taxonomy from Figure 2 of the paper,
containing 9 categories and 31 sub-categories of logical errors to be identified
and rectified by LLMs in the guided correction loop.
"""

from enum import Enum
from typing import Dict, List
from dataclasses import dataclass


class ErrorCategory(Enum):
    """Main error categories from the SQL Error Taxonomy"""
    SYNTAX = "Syntax"
    VALUE = "Value"
    SCHEMA_LINK = "Schema Link"
    JOIN = "Join"
    FILTER = "Filter"
    AGGREGATION = "Aggregation"
    SUBQUERY = "Subquery"
    SET_OPERATIONS = "Set Operations"
    OTHER_ISSUES = "Other Issues"


@dataclass
class ErrorType:
    """Represents a specific error type with its category and description"""
    code: str
    category: ErrorCategory
    description: str
    guidance: str


class SQLErrorTaxonomy:
    """
    Comprehensive SQL error taxonomy for guided error correction.
    
    Based on the taxonomy from Shen et al. and extended for LLM-based correction
    as described in the SQL-of-Thought paper.
    """
    
    ERROR_TYPES = {
        # Syntax Errors
        "sql_syntax_error": ErrorType(
            code="sql_syntax_error",
            category=ErrorCategory.SYNTAX,
            description="SQL syntax is invalid or malformed",
            guidance="Check for missing keywords, incorrect punctuation, or malformed SQL structure"
        ),
        "invalid_alias": ErrorType(
            code="invalid_alias",
            category=ErrorCategory.SYNTAX,
            description="Table or column alias is invalid or conflicts",
            guidance="Ensure aliases are unique and follow SQL naming conventions"
        ),
        
        # Value Errors
        "hardcoded_value": ErrorType(
            code="hardcoded_value",
            category=ErrorCategory.VALUE,
            description="Values are hardcoded instead of being derived from data",
            guidance="Replace hardcoded values with proper column references or calculations"
        ),
        "value_format_wrong": ErrorType(
            code="value_format_wrong",
            category=ErrorCategory.VALUE,
            description="Value format doesn't match expected data type",
            guidance="Ensure value formats match column data types (dates, numbers, strings)"
        ),
        
        # Schema Linking Errors
        "table_missing": ErrorType(
            code="table_missing",
            category=ErrorCategory.SCHEMA_LINK,
            description="Required table is missing from the query",
            guidance="Include all necessary tables based on the question requirements"
        ),
        "col_missing": ErrorType(
            code="col_missing",
            category=ErrorCategory.SCHEMA_LINK,
            description="Required column is missing from the query",
            guidance="Add missing columns that are needed to answer the question"
        ),
        "ambiguous_col": ErrorType(
            code="ambiguous_col",
            category=ErrorCategory.SCHEMA_LINK,
            description="Column reference is ambiguous between multiple tables",
            guidance="Use table prefixes or aliases to disambiguate column references"
        ),
        "incorrect_foreign_key": ErrorType(
            code="incorrect_foreign_key",
            category=ErrorCategory.SCHEMA_LINK,
            description="Foreign key relationship is incorrectly specified",
            guidance="Verify foreign key relationships match the database schema"
        ),
        
        # Join Errors
        "join_missing": ErrorType(
            code="join_missing",
            category=ErrorCategory.JOIN,
            description="Required join is missing from the query",
            guidance="Add necessary joins to connect related tables"
        ),
        "join_wrong_type": ErrorType(
            code="join_wrong_type",
            category=ErrorCategory.JOIN,
            description="Incorrect join type used (INNER, LEFT, RIGHT, FULL)",
            guidance="Choose appropriate join type based on desired result set"
        ),
        "extra_table": ErrorType(
            code="extra_table",
            category=ErrorCategory.JOIN,
            description="Unnecessary table included in the query",
            guidance="Remove tables that don't contribute to the answer"
        ),
        "incorrect_col": ErrorType(
            code="incorrect_col",
            category=ErrorCategory.JOIN,
            description="Wrong column used in join condition",
            guidance="Use correct columns for join conditions based on schema relationships"
        ),
        
        # Filter Errors
        "where_missing": ErrorType(
            code="where_missing",
            category=ErrorCategory.FILTER,
            description="WHERE clause is missing when filtering is required",
            guidance="Add WHERE clause to filter results according to question requirements"
        ),
        "condition_wrong_col": ErrorType(
            code="condition_wrong_col",
            category=ErrorCategory.FILTER,
            description="Wrong column used in filter condition",
            guidance="Use the correct column for filtering based on the question"
        ),
        "condition_type_mismatch": ErrorType(
            code="condition_type_mismatch",
            category=ErrorCategory.FILTER,
            description="Filter condition type doesn't match column data type",
            guidance="Ensure filter conditions match the data type of the column"
        ),
        
        # Aggregation Errors
        "agg_no_groupby": ErrorType(
            code="agg_no_groupby",
            category=ErrorCategory.AGGREGATION,
            description="Aggregate function used without GROUP BY clause",
            guidance="Add GROUP BY clause when using aggregate functions with non-aggregated columns"
        ),
        "groupby_missing_col": ErrorType(
            code="groupby_missing_col",
            category=ErrorCategory.AGGREGATION,
            description="Column missing from GROUP BY clause",
            guidance="Include all non-aggregated SELECT columns in GROUP BY clause"
        ),
        "having_without_groupby": ErrorType(
            code="having_without_groupby",
            category=ErrorCategory.AGGREGATION,
            description="HAVING clause used without GROUP BY",
            guidance="Use WHERE clause for row filtering or add GROUP BY for aggregate filtering"
        ),
        "having_incorrect": ErrorType(
            code="having_incorrect",
            category=ErrorCategory.AGGREGATION,
            description="HAVING clause condition is incorrect",
            guidance="Ensure HAVING conditions work with aggregated results"
        ),
        "having_vs_where": ErrorType(
            code="having_vs_where",
            category=ErrorCategory.AGGREGATION,
            description="HAVING used instead of WHERE or vice versa",
            guidance="Use WHERE for row filtering, HAVING for aggregate filtering"
        ),
        
        # Subquery Errors
        "unused_subquery": ErrorType(
            code="unused_subquery",
            category=ErrorCategory.SUBQUERY,
            description="Subquery is present but not used effectively",
            guidance="Ensure subqueries are properly integrated into the main query"
        ),
        "subquery_missing": ErrorType(
            code="subquery_missing",
            category=ErrorCategory.SUBQUERY,
            description="Required subquery is missing",
            guidance="Add subquery when complex filtering or calculation is needed"
        ),
        "subquery_correlation_error": ErrorType(
            code="subquery_correlation_error",
            category=ErrorCategory.SUBQUERY,
            description="Correlated subquery has incorrect correlation",
            guidance="Ensure correlated subquery properly references outer query columns"
        ),
        
        # Set Operations Errors
        "union_missing": ErrorType(
            code="union_missing",
            category=ErrorCategory.SET_OPERATIONS,
            description="UNION operation is missing when needed",
            guidance="Use UNION to combine results from multiple similar queries"
        ),
        "intersect_missing": ErrorType(
            code="intersect_missing",
            category=ErrorCategory.SET_OPERATIONS,
            description="INTERSECT operation is missing when needed",
            guidance="Use INTERSECT to find common results between queries"
        ),
        "except_missing": ErrorType(
            code="except_missing",
            category=ErrorCategory.SET_OPERATIONS,
            description="EXCEPT operation is missing when needed",
            guidance="Use EXCEPT to exclude specific results from the query"
        ),
        
        # Other Issues
        "order_by_missing": ErrorType(
            code="order_by_missing",
            category=ErrorCategory.OTHER_ISSUES,
            description="ORDER BY clause is missing when sorting is required",
            guidance="Add ORDER BY clause to sort results as specified in the question"
        ),
        "limit_missing": ErrorType(
            code="limit_missing",
            category=ErrorCategory.OTHER_ISSUES,
            description="LIMIT clause is missing when result count restriction is needed",
            guidance="Add LIMIT clause when question asks for top N results"
        ),
        "duplicate_select": ErrorType(
            code="duplicate_select",
            category=ErrorCategory.OTHER_ISSUES,
            description="Duplicate columns in SELECT clause",
            guidance="Remove duplicate column selections or use DISTINCT if needed"
        ),
        "unsupported_function": ErrorType(
            code="unsupported_function",
            category=ErrorCategory.OTHER_ISSUES,
            description="SQL function is not supported by the database",
            guidance="Use database-compatible functions or alternative approaches"
        ),
        "extra_values_selected": ErrorType(
            code="extra_values_selected",
            category=ErrorCategory.OTHER_ISSUES,
            description="More columns selected than needed to answer the question",
            guidance="Select only the columns required to answer the question"
        )
    }
    
    @classmethod
    def get_error_by_code(cls, error_code: str) -> ErrorType:
        """Get error type by its code"""
        return cls.ERROR_TYPES.get(error_code)
    
    @classmethod
    def get_errors_by_category(cls, category: ErrorCategory) -> List[ErrorType]:
        """Get all errors in a specific category"""
        return [error for error in cls.ERROR_TYPES.values() if error.category == category]
    
    @classmethod
    def get_all_error_codes(cls) -> List[str]:
        """Get all error codes"""
        return list(cls.ERROR_TYPES.keys())
    
    @classmethod
    def get_taxonomy_summary(cls) -> str:
        """Get a formatted summary of the error taxonomy for prompts"""
        summary = "SQL Error Taxonomy:\n"
        
        for category in ErrorCategory:
            errors = cls.get_errors_by_category(category)
            if errors:
                summary += f"\n{category.value}:\n"
                for error in errors:
                    summary += f"  - {error.code}: {error.description}\n"
        
        return summary
    
    @classmethod
    def get_guidance_for_errors(cls, error_codes: List[str]) -> Dict[str, str]:
        """Get guidance for a list of error codes"""
        guidance = {}
        for code in error_codes:
            error = cls.get_error_by_code(code)
            if error:
                guidance[code] = error.guidance
        return guidance


# Export for easy access
__all__ = ['SQLErrorTaxonomy', 'ErrorCategory', 'ErrorType']