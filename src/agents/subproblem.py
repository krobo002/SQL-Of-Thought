"""
Subproblem Agent for SQL-of-Thought Framework

This agent decomposes the natural language query into clause-level subproblems 
(e.g., WHERE, GROUP BY, JOIN, DISTINCT, ORDER BY, HAVING, EXCEPT, LIMIT, UNION).
"""

import json
from typing import Dict, List
from src.agents.base import BaseAgent
from src.llm.base import BaseLLM


class SubproblemAgent(BaseAgent):
    """
    Agent for decomposing queries into clause-level subproblems.
    
    Given the natural language question and schema-linked output, this agent
    decomposes the query into clause-level subproblems. Each identified clause
    is expressed as a key-value pair in a structured JSON object.
    """

    def __init__(self, llm: BaseLLM):
        super().__init__(llm)

    def execute(self, question: str, schema_links: dict) -> dict:
        """
        Decomposes the question into clause-level subproblems.

        Args:
            question: The natural language question.
            schema_links: The schema linking output from SchemaLinkingAgent.

        Returns:
            A dictionary containing the identified subproblems by clause type.
        """
        prompt = self._create_prompt(question, schema_links)
        
        # Prepare messages for LLM
        messages = [{"role": "user", "content": prompt}]
        config = {"temperature": 0.0, "max_tokens": 2000}
        
        response = self.llm.invoke(messages, config)
        return self._parse_response(response)

    def _create_prompt(self, question: str, schema_links: dict) -> str:
        """
        Creates the prompt for subproblem identification.
        """
        schema_str = self._format_schema_links(schema_links)
        
        prompt = f"""
You are a Subproblem Agent in the SQL-of-Thought framework. Your task is to decompose a natural language question into clause-level subproblems for SQL generation.

Given:
- A natural language question
- Relevant schema links (tables and columns)

Decompose the query into the following SQL clause types where applicable:
- SELECT: What columns/values to retrieve
- FROM: Which tables to query
- JOIN: How tables should be connected
- WHERE: Row-level filtering conditions
- GROUP BY: Grouping criteria
- HAVING: Group-level filtering conditions
- ORDER BY: Sorting requirements
- LIMIT: Result count restrictions
- DISTINCT: Duplicate removal
- UNION/INTERSECT/EXCEPT: Set operations
- SUBQUERY: Nested query requirements

Question: {question}

Schema Links: {schema_str}

For each applicable clause, provide:
1. The clause type
2. A brief description of what needs to be done
3. The relevant columns/tables involved
4. Any specific conditions or requirements

Return your analysis as a JSON object with clause types as keys and their requirements as values.

Example format:
{{
    "SELECT": "Retrieve customer names and total order amounts",
    "FROM": "customers and orders tables",
    "JOIN": "Connect customers to orders via customer_id",
    "WHERE": "Filter for orders in the last year",
    "GROUP BY": "Group by customer to calculate totals",
    "ORDER BY": "Sort by total amount descending",
    "LIMIT": "Top 10 customers only"
}}

JSON Response:
"""
        return prompt

    def _format_schema_links(self, schema_links: dict) -> str:
        """Format schema links for the prompt."""
        if isinstance(schema_links, str):
            return schema_links
        
        # Handle different possible formats of schema_links
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
                # If it's just a simple dict, convert to string
                return str(schema_links)
        
        return str(schema_links)

    def _parse_response(self, response: str) -> dict:
        """
        Parses the LLM's JSON response into subproblems.
        """
        try:
            # Clean the response if it contains markdown
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                # Handle generic code blocks
                parts = response.split("```")
                if len(parts) >= 3:
                    response = parts[1]
            
            parsed = json.loads(response.strip())
            
            # Validate that we have a dictionary
            if not isinstance(parsed, dict):
                return self._create_fallback_response()
            
            return parsed
            
        except (json.JSONDecodeError, IndexError) as e:
            print(f"Error parsing subproblem response: {e}")
            return self._create_fallback_response()

    def _create_fallback_response(self) -> dict:
        """Create a fallback response when parsing fails."""
        return {
            "SELECT": "Columns to retrieve from the query",
            "FROM": "Tables involved in the query",
            "WHERE": "Filtering conditions if needed",
            "error": "Failed to parse detailed subproblems"
        }

    def get_clause_types(self) -> List[str]:
        """Get all possible SQL clause types this agent can identify."""
        return [
            "SELECT", "FROM", "JOIN", "WHERE", "GROUP BY", 
            "HAVING", "ORDER BY", "LIMIT", "DISTINCT", 
            "UNION", "INTERSECT", "EXCEPT", "SUBQUERY"
        ]

    def validate_subproblems(self, subproblems: dict) -> bool:
        """
        Validate that the subproblems are well-formed.
        
        Args:
            subproblems: The subproblems dictionary to validate
            
        Returns:
            True if valid, False otherwise
        """
        if not isinstance(subproblems, dict):
            return False
        
        # Must have at least SELECT and FROM
        required_clauses = ["SELECT", "FROM"]
        for clause in required_clauses:
            if clause not in subproblems:
                return False
        
        # All values should be non-empty strings
        for clause, description in subproblems.items():
            if not isinstance(description, str) or not description.strip():
                return False
        
        return True
