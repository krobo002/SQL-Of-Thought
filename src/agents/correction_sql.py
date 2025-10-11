"""
Correction SQL Agent for SQL-of-Thought Framework

This agent takes the correction plan and generates the corrected SQL query
while avoiding the previous errors identified in the correction plan.
"""

import re
import json
from typing import Dict, Optional
from src.agents.base import BaseAgent
from src.llm.base import BaseLLM


class CorrectionSQLAgent(BaseAgent):
    """
    Agent for generating corrected SQL queries based on correction plans.
    
    The Correction SQL Agent takes as input the correction plan, the question, 
    the schema, and the incorrect SQL query. Based on the structured guidance, 
    it regenerates the SQL query while avoiding the previous errors.
    """

    def __init__(self, llm: BaseLLM):
        super().__init__(llm)

    def execute(self, question: str, schema_links: dict, failed_sql: str, 
                correction_plan: dict, query_plan: dict = None) -> dict:
        """
        Generates corrected SQL query based on the correction plan.

        Args:
            question: The natural language question.
            schema_links: The schema linking output.
            failed_sql: The original failed SQL query.
            correction_plan: The correction plan from CorrectionPlanAgent.
            query_plan: The original query plan (optional).

        Returns:
            A dictionary containing the corrected SQL and metadata.
        """
        prompt = self._create_prompt(question, schema_links, failed_sql, 
                                   correction_plan, query_plan)
        
        # Prepare messages for LLM
        messages = [{"role": "user", "content": prompt}]
        config = {"temperature": 0.0, "max_tokens": 2500}
        
        response = self.llm.invoke(messages, config)
        return self._parse_and_process_response(response, correction_plan)

    def _create_prompt(self, question: str, schema_links: dict, failed_sql: str,
                      correction_plan: dict, query_plan: dict = None) -> str:
        """
        Creates the prompt for corrected SQL generation.
        """
        schema_str = self._format_schema_links(schema_links)
        plan_str = self._format_correction_plan(correction_plan)
        original_plan_str = self._format_query_plan(query_plan) if query_plan else ""
        
        prompt = f"""
You are a Correction SQL Agent in the SQL-of-Thought framework. Your task is to generate a corrected SQL query based on the detailed correction plan provided.

Given:
- Natural language question
- Database schema information
- Failed SQL query
- Detailed correction plan with identified errors and fixes
- Original query plan (if available)

Generate a corrected SQL query that:
1. Addresses ALL issues identified in the correction plan
2. Follows the correction steps precisely
3. Uses correct table and column names from the schema
4. Avoids the specific errors mentioned in the correction plan
5. Maintains the original intent of answering the natural language question

Question: {question}

Schema Information: {schema_str}

Original Query Plan: {original_plan_str}

Failed SQL Query: {failed_sql}

Correction Plan: {plan_str}

Instructions for Correction:
- Carefully review each identified error and correction step
- Apply fixes in the order specified by priority (high → medium → low)
- Ensure the corrected query addresses the root causes mentioned in the plan
- Use proper SQL syntax (SQLite compatible)
- Double-check that all table and column names match the schema exactly
- Verify that joins, conditions, and aggregations are logically correct
- Do not include explanations or comments in the SQL
- Do not add trailing semicolons

Important: Focus on the specific issues identified in the correction plan. Do not make unnecessary changes to parts of the query that were working correctly.

Corrected SQL Query:
"""
        return prompt

    def _format_schema_links(self, schema_links: dict) -> str:
        """Format schema links for the prompt."""
        if isinstance(schema_links, str):
            return schema_links
        
        if isinstance(schema_links, dict):
            if 'tables' in schema_links:
                tables_info = []
                for table_info in schema_links.get('tables', []):
                    if isinstance(table_info, str):
                        tables_info.append(table_info)
                    elif isinstance(table_info, dict):
                        table_name = table_info.get('name', 'unknown')
                        columns = table_info.get('columns', [])
                        tables_info.append(f"Table {table_name}: {', '.join(columns)}")
                return "\n".join(tables_info)
            else:
                return str(schema_links)
        
        return str(schema_links)

    def _format_correction_plan(self, correction_plan: dict) -> str:
        """Format correction plan for the prompt."""
        if not isinstance(correction_plan, dict):
            return str(correction_plan)
        
        formatted = []
        
        # Add error analysis
        if 'error_analysis' in correction_plan:
            formatted.append(f"Error Analysis: {correction_plan['error_analysis']}")
        
        # Add identified errors
        if 'identified_errors' in correction_plan and isinstance(correction_plan['identified_errors'], list):
            formatted.append("\nIdentified Errors:")
            for error in correction_plan['identified_errors']:
                if isinstance(error, dict):
                    formatted.append(f"  - {error.get('error_code', 'unknown')}: {error.get('description', 'N/A')}")
                    formatted.append(f"    Location: {error.get('location', 'Unknown')}")
        
        # Add correction steps
        if 'correction_steps' in correction_plan and isinstance(correction_plan['correction_steps'], list):
            # Sort by priority (high, medium, low)
            priority_order = {'high': 1, 'medium': 2, 'low': 3}
            sorted_steps = sorted(
                correction_plan['correction_steps'], 
                key=lambda x: (priority_order.get(x.get('priority', 'medium'), 2), x.get('step', 0))
            )
            
            formatted.append("\nCorrection Steps (in priority order):")
            for step in sorted_steps:
                if isinstance(step, dict):
                    formatted.append(f"  {step.get('step', '?')}. [{step.get('priority', 'medium').upper()}] {step.get('action', 'N/A')}")
                    formatted.append(f"     Reasoning: {step.get('reasoning', 'N/A')}")
        
        # Add expected outcome
        if 'expected_outcome' in correction_plan:
            formatted.append(f"\nExpected Outcome: {correction_plan['expected_outcome']}")
        
        return "\n".join(formatted)

    def _format_query_plan(self, query_plan: dict) -> str:
        """Format original query plan for the prompt."""
        if isinstance(query_plan, dict):
            formatted = []
            if 'reasoning' in query_plan:
                formatted.append(f"Original Reasoning: {query_plan['reasoning']}")
            if 'execution_steps' in query_plan:
                formatted.append("Original Execution Steps:")
                for i, step in enumerate(query_plan['execution_steps'], 1):
                    formatted.append(f"  {i}. {step}")
            return "\n".join(formatted)
        return str(query_plan)

    def _parse_and_process_response(self, response: str, correction_plan: dict) -> dict:
        """
        Parses and post-processes the corrected SQL response.
        """
        # Extract SQL from response
        corrected_sql = self._extract_sql(response)
        
        # Post-process the SQL
        processed_sql = self._post_process_sql(corrected_sql)
        
        # Validate the SQL
        is_valid, validation_message = self._validate_sql_syntax(processed_sql)
        
        # Check if corrections were applied
        corrections_applied = self._verify_corrections_applied(processed_sql, correction_plan)
        
        return {
            "sql": processed_sql,
            "raw_response": response,
            "is_valid": is_valid,
            "validation_message": validation_message,
            "corrections_applied": corrections_applied,
            "correction_attempt": True
        }

    def _extract_sql(self, response: str) -> str:
        """
        Extracts SQL query from the LLM response.
        """
        # Remove markdown code blocks if present
        if "```sql" in response:
            sql_match = re.search(r'```sql\n(.*?)\n```', response, re.DOTALL)
            if sql_match:
                return sql_match.group(1).strip()
        elif "```" in response:
            # Handle generic code blocks
            parts = response.split("```")
            if len(parts) >= 3:
                return parts[1].strip()
        
        # Clean up the response by removing common prefixes/suffixes
        sql = response.strip()
        
        # Remove common prefixes
        prefixes_to_remove = [
            "Corrected SQL Query:",
            "Corrected SQL:",
            "SQL Query:",
            "Query:",
            "SQL:",
            "Here's the corrected SQL query:",
            "The corrected SQL query is:",
            "Corrected query:",
        ]
        
        for prefix in prefixes_to_remove:
            if sql.startswith(prefix):
                sql = sql[len(prefix):].strip()
        
        return sql

    def _post_process_sql(self, sql: str) -> str:
        """
        Post-processes the corrected SQL to remove artifacts and ensure validity.
        """
        if not sql:
            return sql
        
        # Remove trailing semicolons
        sql = sql.rstrip(';').strip()
        
        # Remove any remaining natural language fragments at the end
        natural_language_patterns = [
            r'\s*This corrected query.*$',
            r'\s*The corrected query.*$',
            r'\s*This query now.*$',
            r'\s*Note:.*$',
            r'\s*Explanation:.*$',
            r'\s*The fix.*$',
        ]
        
        for pattern in natural_language_patterns:
            sql = re.sub(pattern, '', sql, flags=re.IGNORECASE | re.DOTALL)
        
        # Clean up extra whitespace
        sql = ' '.join(sql.split())
        
        # Ensure proper spacing around SQL keywords
        sql = self._normalize_sql_formatting(sql)
        
        return sql.strip()

    def _normalize_sql_formatting(self, sql: str) -> str:
        """
        Normalizes SQL formatting for better readability.
        """
        # Add proper spacing around common SQL keywords
        keywords = ['SELECT', 'FROM', 'WHERE', 'JOIN', 'INNER JOIN', 'LEFT JOIN', 
                   'RIGHT JOIN', 'FULL JOIN', 'GROUP BY', 'ORDER BY', 'HAVING', 
                   'LIMIT', 'UNION', 'INTERSECT', 'EXCEPT', 'AND', 'OR']
        
        for keyword in keywords:
            # Ensure proper spacing around keywords (case insensitive)
            pattern = r'\b' + re.escape(keyword) + r'\b'
            sql = re.sub(pattern, keyword, sql, flags=re.IGNORECASE)
        
        return sql

    def _validate_sql_syntax(self, sql: str) -> tuple[bool, str]:
        """
        Performs basic SQL syntax validation.
        
        Returns:
            Tuple of (is_valid, validation_message)
        """
        if not sql or not sql.strip():
            return False, "Empty corrected SQL query"
        
        # Check for required SQL elements
        sql_upper = sql.upper()
        
        if not sql_upper.startswith('SELECT'):
            return False, "Corrected query must start with SELECT"
        
        if 'FROM' not in sql_upper:
            return False, "Corrected query must contain FROM clause"
        
        # Check for balanced parentheses
        open_parens = sql.count('(')
        close_parens = sql.count(')')
        if open_parens != close_parens:
            return False, f"Unbalanced parentheses in corrected query: {open_parens} open, {close_parens} close"
        
        return True, "Basic syntax validation passed for corrected query"

    def _verify_corrections_applied(self, corrected_sql: str, correction_plan: dict) -> dict:
        """
        Verifies that the identified corrections were actually applied.
        
        Returns:
            Dictionary containing information about applied corrections
        """
        verification_results = {
            "total_issues": 0,
            "addressed_issues": [],
            "potential_remaining_issues": [],
            "verification_notes": []
        }
        
        if not isinstance(correction_plan, dict) or 'identified_errors' not in correction_plan:
            verification_results["verification_notes"].append("No correction plan available for verification")
            return verification_results
        
        identified_errors = correction_plan.get('identified_errors', [])
        verification_results["total_issues"] = len(identified_errors)
        
        sql_upper = corrected_sql.upper()
        
        for error in identified_errors:
            if not isinstance(error, dict):
                continue
                
            error_code = error.get('error_code', 'unknown')
            
            # Basic verification based on error types
            if error_code == 'table_missing':
                # This would require more sophisticated analysis
                verification_results["addressed_issues"].append(f"Checked for missing tables (manual verification needed)")
            
            elif error_code == 'col_missing':
                verification_results["addressed_issues"].append(f"Checked for missing columns (manual verification needed)")
            
            elif error_code == 'join_missing':
                if 'JOIN' in sql_upper:
                    verification_results["addressed_issues"].append("Added JOIN clause")
                else:
                    verification_results["potential_remaining_issues"].append("JOIN clause may still be missing")
            
            elif error_code == 'where_missing':
                if 'WHERE' in sql_upper:
                    verification_results["addressed_issues"].append("Added WHERE clause")
                else:
                    verification_results["potential_remaining_issues"].append("WHERE clause may still be missing")
            
            elif error_code == 'groupby_missing_col':
                if 'GROUP BY' in sql_upper:
                    verification_results["addressed_issues"].append("Added/corrected GROUP BY clause")
                else:
                    verification_results["potential_remaining_issues"].append("GROUP BY issue may not be resolved")
            
            elif error_code == 'order_by_missing':
                if 'ORDER BY' in sql_upper:
                    verification_results["addressed_issues"].append("Added ORDER BY clause")
                else:
                    verification_results["potential_remaining_issues"].append("ORDER BY clause may still be missing")
            
            elif error_code == 'limit_missing':
                if 'LIMIT' in sql_upper:
                    verification_results["addressed_issues"].append("Added LIMIT clause")
                else:
                    verification_results["potential_remaining_issues"].append("LIMIT clause may still be missing")
            
            else:
                verification_results["addressed_issues"].append(f"Attempted to address {error_code}")
        
        return verification_results

    def compare_with_original(self, original_sql: str, corrected_sql: str) -> dict:
        """
        Compares the corrected SQL with the original to highlight changes.
        
        Args:
            original_sql: The original failed SQL query
            corrected_sql: The corrected SQL query
            
        Returns:
            Dictionary containing comparison results
        """
        comparison = {
            "changes_detected": original_sql.strip() != corrected_sql.strip(),
            "original_length": len(original_sql),
            "corrected_length": len(corrected_sql),
            "added_keywords": [],
            "removed_keywords": [],
            "structural_changes": []
        }
        
        # Compare SQL keywords
        sql_keywords = ['SELECT', 'FROM', 'WHERE', 'JOIN', 'INNER JOIN', 'LEFT JOIN', 
                       'GROUP BY', 'ORDER BY', 'HAVING', 'LIMIT', 'UNION', 'INTERSECT', 'EXCEPT']
        
        original_upper = original_sql.upper()
        corrected_upper = corrected_sql.upper()
        
        for keyword in sql_keywords:
            original_has = keyword in original_upper
            corrected_has = keyword in corrected_upper
            
            if not original_has and corrected_has:
                comparison["added_keywords"].append(keyword)
            elif original_has and not corrected_has:
                comparison["removed_keywords"].append(keyword)
        
        # Detect structural changes
        if len(comparison["added_keywords"]) > 0:
            comparison["structural_changes"].append(f"Added clauses: {', '.join(comparison['added_keywords'])}")
        
        if len(comparison["removed_keywords"]) > 0:
            comparison["structural_changes"].append(f"Removed clauses: {', '.join(comparison['removed_keywords'])}")
        
        if comparison["corrected_length"] > comparison["original_length"] * 1.2:
            comparison["structural_changes"].append("Significantly expanded query")
        elif comparison["corrected_length"] < comparison["original_length"] * 0.8:
            comparison["structural_changes"].append("Significantly simplified query")
        
        return comparison
