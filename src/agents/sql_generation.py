"""
SQL Generation Agent for SQL-of-Thought Framework

This agent consumes the natural language question and query plan to generate
the executable SQL query with post-processing to ensure syntactic validity.
"""

import re
import json
from typing import Dict, Optional
from src.agents.base import BaseAgent
from src.llm.base import BaseLLM


class SQLGenerationAgent(BaseAgent):
    """
    Agent for generating executable SQL queries.
    
    The SQL Agent consumes the natural language question and the query plan to 
    generate the executable SQL query. Post-processing removes extraneous artifacts 
    such as trailing semicolons or natural language fragments.
    """

    def __init__(self, llm: BaseLLM):
        super().__init__(llm)

    def execute(self, question: str, query_plan: dict, schema_links: dict) -> dict:
        """
        Generates executable SQL query based on the query plan.

        Args:
            question: The natural language question.
            query_plan: The query plan from QueryPlanAgent.
            schema_links: The schema linking output.

        Returns:
            A dictionary containing the generated SQL and metadata.
        """
        prompt = self._create_prompt(question, query_plan, schema_links)
        
        # Prepare messages for LLM
        messages = [{"role": "user", "content": prompt}]
        config = {"temperature": 0.0, "max_tokens": 2000}
        
        response = self.llm.invoke(messages, config)
        return self._parse_and_process_response(response)

    def _create_prompt(self, question: str, query_plan: dict, schema_links: dict) -> str:
        """
        Creates the prompt for SQL generation.
        """
        plan_str = self._format_query_plan(query_plan)
        schema_str = self._format_schema_links(schema_links)
        
        prompt = f"""
You are a SQL Generation Agent in the SQL-of-Thought framework. Your task is to generate a syntactically correct and executable SQL query based on the provided query plan.

Given:
- Natural language question
- Structured query plan with execution steps
- Relevant schema information

Generate a SQL query that:
1. Follows the execution plan precisely
2. Uses correct table and column names from the schema
3. Is syntactically valid and executable
4. Answers the natural language question accurately

Question: {question}

Query Plan: {plan_str}

Schema Information: {schema_str}

Instructions:
- Generate ONLY the SQL query
- Use proper SQL syntax (SQLite compatible)
- Include appropriate JOINs, WHERE conditions, GROUP BY, ORDER BY, LIMIT as specified in the plan
- Use correct table and column names exactly as shown in the schema
- Do not include explanations or comments in the SQL
- Do not add trailing semicolons or extra formatting

SQL Query:
"""
        return prompt

    def _format_query_plan(self, plan: dict) -> str:
        """Format query plan for the prompt."""
        if isinstance(plan, dict):
            formatted = []
            
            # Include reasoning
            if 'reasoning' in plan:
                formatted.append(f"Reasoning: {plan['reasoning']}")
            
            # Include execution steps
            if 'execution_steps' in plan and isinstance(plan['execution_steps'], list):
                formatted.append("Execution Steps:")
                for i, step in enumerate(plan['execution_steps'], 1):
                    formatted.append(f"  {i}. {step}")
            
            # Include other plan components
            for key, value in plan.items():
                if key not in ['reasoning', 'execution_steps'] and key != 'error':
                    formatted.append(f"{key}: {value}")
            
            return "\n".join(formatted)
        
        return str(plan)

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

    def _parse_and_process_response(self, response: str) -> dict:
        """
        Parses and post-processes the LLM's SQL response.
        """
        # Extract SQL from response
        sql_query = self._extract_sql(response)
        
        # Post-process the SQL
        processed_sql = self._post_process_sql(sql_query)
        
        # Validate the SQL
        is_valid, validation_message = self._validate_sql_syntax(processed_sql)
        
        return {
            "sql": processed_sql,
            "raw_response": response,
            "is_valid": is_valid,
            "validation_message": validation_message,
            "post_processed": True
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
            "SQL Query:",
            "Query:",
            "SQL:",
            "Here's the SQL query:",
            "The SQL query is:",
        ]
        
        for prefix in prefixes_to_remove:
            if sql.startswith(prefix):
                sql = sql[len(prefix):].strip()
        
        return sql

    def _post_process_sql(self, sql: str) -> str:
        """
        Post-processes the SQL to remove artifacts and ensure validity.
        """
        if not sql:
            return sql
        
        # Remove trailing semicolons
        sql = sql.rstrip(';').strip()
        
        # Remove any remaining natural language fragments at the end
        # Look for patterns like "This query..." or "The above query..."
        natural_language_patterns = [
            r'\s*This query.*$',
            r'\s*The above query.*$',
            r'\s*Note:.*$',
            r'\s*Explanation:.*$',
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
            return False, "Empty SQL query"
        
        # Check for required SQL elements
        sql_upper = sql.upper()
        
        if not sql_upper.startswith('SELECT'):
            return False, "Query must start with SELECT"
        
        if 'FROM' not in sql_upper:
            return False, "Query must contain FROM clause"
        
        # Check for balanced parentheses
        open_parens = sql.count('(')
        close_parens = sql.count(')')
        if open_parens != close_parens:
            return False, f"Unbalanced parentheses: {open_parens} open, {close_parens} close"
        
        # Check for basic SQL injection patterns (simple validation)
        suspicious_patterns = [
            r';\s*DROP\s+TABLE',
            r';\s*DELETE\s+FROM',
            r';\s*UPDATE\s+\w+\s+SET',
            r'UNION\s+SELECT.*--',
        ]
        
        for pattern in suspicious_patterns:
            if re.search(pattern, sql, re.IGNORECASE):
                return False, f"Potentially unsafe SQL pattern detected"
        
        return True, "Basic syntax validation passed"

    def get_sql_metadata(self, sql: str) -> dict:
        """
        Extracts metadata from the generated SQL query.
        
        Args:
            sql: The SQL query string
            
        Returns:
            Dictionary containing SQL metadata
        """
        if not sql:
            return {}
        
        sql_upper = sql.upper()
        
        metadata = {
            "query_type": "SELECT",  # Assuming all queries are SELECT for now
            "has_joins": any(join in sql_upper for join in ['JOIN', 'INNER JOIN', 'LEFT JOIN', 'RIGHT JOIN']),
            "has_where": 'WHERE' in sql_upper,
            "has_group_by": 'GROUP BY' in sql_upper,
            "has_order_by": 'ORDER BY' in sql_upper,
            "has_having": 'HAVING' in sql_upper,
            "has_limit": 'LIMIT' in sql_upper,
            "has_subquery": '(' in sql and 'SELECT' in sql[sql.find('('):],
            "has_aggregation": any(func in sql_upper for func in ['COUNT(', 'SUM(', 'AVG(', 'MAX(', 'MIN(']),
            "estimated_complexity": "unknown"
        }
        
        # Estimate complexity based on features
        complexity_score = 0
        if metadata["has_joins"]: complexity_score += 2
        if metadata["has_where"]: complexity_score += 1
        if metadata["has_group_by"]: complexity_score += 2
        if metadata["has_subquery"]: complexity_score += 3
        if metadata["has_aggregation"]: complexity_score += 1
        
        if complexity_score <= 2:
            metadata["estimated_complexity"] = "simple"
        elif complexity_score <= 5:
            metadata["estimated_complexity"] = "moderate"
        else:
            metadata["estimated_complexity"] = "complex"
        
        return metadata
