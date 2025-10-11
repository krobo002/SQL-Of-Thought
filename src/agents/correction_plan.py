"""
Correction Plan Agent for SQL-of-Thought Framework

This agent initiates the correction loop by analyzing failed SQL queries and generating
chain-of-thought correction plans using the comprehensive error taxonomy.
"""

import json
import re
from typing import Dict, List, Optional
from src.agents.base import BaseAgent
from src.llm.base import BaseLLM
from src.error_taxonomy import SQLErrorTaxonomy


class CorrectionPlanAgent(BaseAgent):
    """
    Agent for generating structured correction plans for failed SQL queries.
    
    The Correction Plan Agent initiates the correction loop by analyzing the failed SQL query 
    in the context of the natural language question, schema, and execution results. Unlike 
    systems that rely solely on execution feedback, this agent is additionally guided by 
    an error taxonomy derived from comprehensive SQL error categorization.
    """

    def __init__(self, llm: BaseLLM):
        super().__init__(llm)
        self.error_taxonomy = SQLErrorTaxonomy()

    def execute(self, question: str, schema_links: dict, failed_sql: str, 
                execution_error: str, query_plan: dict = None) -> dict:
        """
        Generates a correction plan for a failed SQL query.

        Args:
            question: The natural language question.
            schema_links: The schema linking output.
            failed_sql: The SQL query that failed.
            execution_error: The execution error message.
            query_plan: The original query plan (optional).

        Returns:
            A dictionary containing the correction plan and identified errors.
        """
        prompt = self._create_prompt(question, schema_links, failed_sql, 
                                   execution_error, query_plan)
        
        # Prepare messages for LLM
        messages = [{"role": "user", "content": prompt}]
        config = {"temperature": 0.0, "max_tokens": 3000}
        
        response = self.llm.invoke(messages, config)
        return self._parse_response(response)

    def _create_prompt(self, question: str, schema_links: dict, failed_sql: str,
                      execution_error: str, query_plan: dict = None) -> str:
        """
        Creates the Chain-of-Thought prompt for correction plan generation.
        """
        schema_str = self._format_schema_links(schema_links)
        plan_str = self._format_query_plan(query_plan) if query_plan else "No query plan available"
        taxonomy_summary = self.error_taxonomy.get_taxonomy_summary()
        
        prompt = f"""
You are a Correction Plan Agent in the SQL-of-Thought framework. Your task is to analyze a failed SQL query and generate a structured correction plan using Chain-of-Thought reasoning and a comprehensive error taxonomy.

IMPORTANT: Do NOT generate corrected SQL code. Your role is to diagnose the problem and create a correction plan.

Given:
- Natural language question
- Database schema information
- Failed SQL query
- Execution error message
- Query plan (if available)
- Comprehensive error taxonomy

Use Chain-of-Thought reasoning to:
1. Identify the root cause of the failure
2. Categorize the error using the provided taxonomy
3. Generate a step-by-step correction plan

Question: {question}

Schema Information: {schema_str}

Query Plan: {plan_str}

Failed SQL Query: {failed_sql}

Execution Error: {execution_error}

Error Taxonomy Reference:
{taxonomy_summary}

## Chain-of-Thought Analysis:

Step 1: Error Analysis
- What is the exact error message telling us?
- Is this a syntax error, logical error, or schema mismatch?
- What part of the query is causing the issue?

Step 2: Taxonomy Classification
- Which error category does this fall into? (Syntax, Value, Schema Link, Join, Filter, Aggregation, Subquery, Set Operations, Other Issues)
- What specific error type from the taxonomy matches this issue?
- Are there multiple error types involved?

Step 3: Root Cause Investigation
- Why did this error occur?
- What was the intent vs. what was implemented?
- Are there schema-related issues (missing tables, wrong column names)?
- Are there logical issues (wrong joins, incorrect conditions)?

Step 4: Impact Assessment
- How does this error affect the query results?
- What would happen if we ignore this error?
- Are there cascading effects to consider?

Step 5: Correction Strategy
- What specific changes are needed?
- In what order should corrections be applied?
- Are there alternative approaches to consider?

## Correction Plan:
Provide a structured correction plan as JSON:
{{
    "error_analysis": "Detailed analysis of what went wrong",
    "identified_errors": [
        {{
            "error_code": "error_code_from_taxonomy",
            "category": "Error category",
            "description": "What the error is",
            "location": "Where in the query the error occurs"
        }}
    ],
    "root_causes": [
        "Primary cause 1",
        "Secondary cause 2"
    ],
    "correction_steps": [
        {{
            "step": 1,
            "action": "What to fix",
            "reasoning": "Why this fix is needed",
            "priority": "high/medium/low"
        }}
    ],
    "expected_outcome": "What the corrected query should achieve",
    "alternative_approaches": ["Alternative approach 1", "Alternative approach 2"],
    "validation_checks": ["Check 1", "Check 2"]
}}

JSON Response:
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

    def _format_query_plan(self, query_plan: dict) -> str:
        """Format query plan for the prompt."""
        if isinstance(query_plan, dict):
            formatted = []
            if 'reasoning' in query_plan:
                formatted.append(f"Reasoning: {query_plan['reasoning']}")
            if 'execution_steps' in query_plan:
                formatted.append("Execution Steps:")
                for i, step in enumerate(query_plan['execution_steps'], 1):
                    formatted.append(f"  {i}. {step}")
            return "\n".join(formatted)
        return str(query_plan)

    def _parse_response(self, response: str) -> dict:
        """
        Parses the LLM's JSON response into a structured correction plan.
        """
        try:
            # Clean the response if it contains markdown
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                parts = response.split("```")
                if len(parts) >= 3:
                    response = parts[1]
            
            parsed = json.loads(response.strip())
            
            # Validate that we have a dictionary with required fields
            if not isinstance(parsed, dict):
                return self._create_fallback_plan()
            
            # Ensure required fields exist
            required_fields = ["error_analysis", "identified_errors", "correction_steps"]
            for field in required_fields:
                if field not in parsed:
                    if field == "identified_errors":
                        parsed[field] = []
                    elif field == "correction_steps":
                        parsed[field] = []
                    else:
                        parsed[field] = f"Missing {field} information"
            
            # Validate error structures
            parsed = self._validate_and_fix_structure(parsed)
            
            return parsed
            
        except (json.JSONDecodeError, IndexError) as e:
            print(f"Error parsing correction plan response: {e}")
            return self._create_fallback_plan()

    def _validate_and_fix_structure(self, plan: dict) -> dict:
        """Validate and fix the structure of the correction plan."""
        
        # Ensure identified_errors is a list of properly structured errors
        if "identified_errors" in plan and isinstance(plan["identified_errors"], list):
            fixed_errors = []
            for error in plan["identified_errors"]:
                if isinstance(error, dict):
                    # Ensure required error fields
                    fixed_error = {
                        "error_code": error.get("error_code", "unknown_error"),
                        "category": error.get("category", "Other Issues"),
                        "description": error.get("description", "Unknown error"),
                        "location": error.get("location", "Unknown location")
                    }
                    fixed_errors.append(fixed_error)
            plan["identified_errors"] = fixed_errors
        
        # Ensure correction_steps is a list of properly structured steps
        if "correction_steps" in plan and isinstance(plan["correction_steps"], list):
            fixed_steps = []
            for i, step in enumerate(plan["correction_steps"], 1):
                if isinstance(step, dict):
                    fixed_step = {
                        "step": step.get("step", i),
                        "action": step.get("action", "Undefined action"),
                        "reasoning": step.get("reasoning", "No reasoning provided"),
                        "priority": step.get("priority", "medium")
                    }
                    fixed_steps.append(fixed_step)
                elif isinstance(step, str):
                    # Handle case where steps are just strings
                    fixed_steps.append({
                        "step": i,
                        "action": step,
                        "reasoning": "Converted from string format",
                        "priority": "medium"
                    })
            plan["correction_steps"] = fixed_steps
        
        # Ensure other fields are lists if they should be
        list_fields = ["root_causes", "alternative_approaches", "validation_checks"]
        for field in list_fields:
            if field in plan and not isinstance(plan[field], list):
                if isinstance(plan[field], str):
                    plan[field] = [plan[field]]
                else:
                    plan[field] = []
        
        return plan

    def _create_fallback_plan(self) -> dict:
        """Create a fallback correction plan when parsing fails."""
        return {
            "error_analysis": "Failed to parse detailed error analysis",
            "identified_errors": [
                {
                    "error_code": "unknown_error",
                    "category": "Other Issues",
                    "description": "Could not identify specific error type",
                    "location": "Unknown"
                }
            ],
            "root_causes": ["Parsing failed - manual analysis required"],
            "correction_steps": [
                {
                    "step": 1,
                    "action": "Manually review the failed SQL query",
                    "reasoning": "Automated correction plan generation failed",
                    "priority": "high"
                }
            ],
            "expected_outcome": "Corrected SQL query that executes successfully",
            "alternative_approaches": ["Manual SQL debugging"],
            "validation_checks": ["Syntax validation", "Semantic validation"],
            "parsing_error": True
        }

    def categorize_error_from_message(self, error_message: str) -> List[str]:
        """
        Attempts to categorize error based on the error message.
        
        Args:
            error_message: The database execution error message
            
        Returns:
            List of potential error codes from the taxonomy
        """
        error_message_lower = error_message.lower()
        potential_errors = []
        
        # Syntax errors
        if any(keyword in error_message_lower for keyword in ['syntax error', 'invalid syntax']):
            potential_errors.append("sql_syntax_error")
        
        # Missing table/column errors
        if any(keyword in error_message_lower for keyword in ['no such table', 'table doesn\'t exist']):
            potential_errors.append("table_missing")
        
        if any(keyword in error_message_lower for keyword in ['no such column', 'unknown column']):
            potential_errors.append("col_missing")
        
        # Ambiguous column errors
        if 'ambiguous' in error_message_lower:
            potential_errors.append("ambiguous_col")
        
        # Aggregation errors
        if any(keyword in error_message_lower for keyword in ['must appear in group by', 'not a group by expression']):
            potential_errors.append("groupby_missing_col")
        
        # Join errors
        if any(keyword in error_message_lower for keyword in ['foreign key', 'reference']):
            potential_errors.append("incorrect_foreign_key")
        
        return potential_errors if potential_errors else ["unknown_error"]

    def get_plan_summary(self, plan: dict) -> str:
        """
        Get a text summary of the correction plan.
        
        Args:
            plan: The correction plan dictionary
            
        Returns:
            A formatted string summary of the plan
        """
        if not isinstance(plan, dict):
            return "Invalid correction plan format"
        
        summary = "Correction Plan Summary:\n"
        summary += f"Error Analysis: {plan.get('error_analysis', 'N/A')}\n\n"
        
        if 'identified_errors' in plan and isinstance(plan['identified_errors'], list):
            summary += "Identified Errors:\n"
            for error in plan['identified_errors']:
                if isinstance(error, dict):
                    summary += f"  - {error.get('error_code', 'unknown')}: {error.get('description', 'N/A')}\n"
        
        if 'correction_steps' in plan and isinstance(plan['correction_steps'], list):
            summary += "\nCorrection Steps:\n"
            for step in plan['correction_steps']:
                if isinstance(step, dict):
                    summary += f"  {step.get('step', '?')}. {step.get('action', 'N/A')} (Priority: {step.get('priority', 'unknown')})\n"
        
        return summary
