"""
Query Plan Agent for SQL-of-Thought Framework

This agent generates a step-by-step execution plan using Chain-of-Thought reasoning
that maps the user's intent to the schema and subproblems before SQL generation.
"""

import json
from typing import Dict, List
from src.agents.base import BaseAgent
from src.llm.base import BaseLLM


class QueryPlanAgent(BaseAgent):
    """
    Agent for generating structured query execution plans.
    
    The Query Plan Agent generates a step-by-step execution plan that maps the user's 
    intent to the schema and subproblems. Unlike prior work, this agent is explicitly 
    prompted to perform chain-of-thought reasoning to explain intermediate decisions.
    """

    def __init__(self, llm: BaseLLM):
        super().__init__(llm)

    def execute(self, question: str, schema_links: dict, subproblems: dict) -> dict:
        """
        Generates a structured query plan using Chain-of-Thought reasoning.

        Args:
            question: The natural language question.
            schema_links: The schema linking output.
            subproblems: The subproblems identified by SubproblemAgent.

        Returns:
            A dictionary containing the structured query plan.
        """
        prompt = self._create_prompt(question, schema_links, subproblems)
        
        # Prepare messages for LLM
        messages = [{"role": "user", "content": prompt}]
        config = {"temperature": 0.0, "max_tokens": 3000}
        
        response = self.llm.invoke(messages, config)
        return self._parse_response(response)

    def _create_prompt(self, question: str, schema_links: dict, subproblems: dict) -> str:
        """
        Creates the Chain-of-Thought prompt for query plan generation.
        """
        schema_str = self._format_schema_links(schema_links)
        subproblems_str = self._format_subproblems(subproblems)
        
        prompt = f"""
You are a Query Plan Agent in the SQL-of-Thought framework. Your task is to generate a step-by-step execution plan using Chain-of-Thought reasoning that maps the user's intent to the database schema and identified subproblems.

IMPORTANT: You must NOT generate executable SQL code. Your role is to create a procedural plan that will guide SQL generation.

Given:
- Natural language question
- Relevant schema links
- Identified subproblems

Use Chain-of-Thought reasoning to create a detailed execution plan that explains:
1. What data is needed and why
2. Which tables to access and in what order
3. How tables should be connected (join strategy)
4. What filtering/grouping/sorting is required
5. The logical flow of operations

Question: {question}

Schema Links: {schema_str}

Subproblems: {subproblems_str}

Now, think step by step and create a detailed query plan:

## Chain-of-Thought Reasoning:

Step 1: Understanding the Question
- What is the user asking for?
- What type of result is expected?
- Are there any implicit requirements?

Step 2: Schema Analysis
- Which tables contain the required information?
- What are the key relationships between tables?
- Are there any potential ambiguities?

Step 3: Join Strategy
- How should tables be connected?
- What type of joins are needed?
- What is the optimal join order?

Step 4: Filtering Strategy
- What conditions need to be applied?
- Should filters be applied before or after joins?
- Are there any aggregate conditions?

Step 5: Grouping and Aggregation
- Is grouping required?
- What aggregation functions are needed?
- How should results be aggregated?

Step 6: Sorting and Limiting
- How should results be ordered?
- Are there any result count limitations?
- What is the final output format?

## Final Query Plan:
Provide a structured plan as JSON with these components:
{{
    "reasoning": "Your chain-of-thought analysis",
    "data_requirements": "What data is needed",
    "table_access_order": ["table1", "table2", ...],
    "join_strategy": "How tables should be connected",
    "filtering_plan": "What conditions to apply",
    "aggregation_plan": "Grouping and aggregation strategy",
    "sorting_plan": "How to order results",
    "execution_steps": [
        "Step 1: ...",
        "Step 2: ...",
        ...
    ]
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

    def _format_subproblems(self, subproblems: dict) -> str:
        """Format subproblems for the prompt."""
        if isinstance(subproblems, dict):
            formatted = []
            for clause, description in subproblems.items():
                formatted.append(f"{clause}: {description}")
            return "\n".join(formatted)
        return str(subproblems)

    def _parse_response(self, response: str) -> dict:
        """
        Parses the LLM's JSON response into a structured query plan.
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
            required_fields = ["reasoning", "execution_steps"]
            for field in required_fields:
                if field not in parsed:
                    parsed[field] = f"Missing {field} information"
            
            return parsed
            
        except (json.JSONDecodeError, IndexError) as e:
            print(f"Error parsing query plan response: {e}")
            return self._create_fallback_plan()

    def _create_fallback_plan(self) -> dict:
        """Create a fallback plan when parsing fails."""
        return {
            "reasoning": "Chain-of-thought reasoning failed to parse",
            "data_requirements": "Identify required data from the question",
            "table_access_order": ["unknown"],
            "join_strategy": "Determine appropriate joins",
            "filtering_plan": "Apply necessary filters",
            "aggregation_plan": "Group and aggregate as needed",
            "sorting_plan": "Sort results appropriately",
            "execution_steps": [
                "Step 1: Identify data requirements",
                "Step 2: Determine table relationships", 
                "Step 3: Plan joins and filters",
                "Step 4: Apply aggregation if needed",
                "Step 5: Sort and limit results"
            ],
            "error": "Failed to parse detailed query plan"
        }

    def validate_plan(self, plan: dict) -> bool:
        """
        Validate that the query plan is well-formed.
        
        Args:
            plan: The query plan dictionary to validate
            
        Returns:
            True if valid, False otherwise
        """
        if not isinstance(plan, dict):
            return False
        
        # Must have reasoning and execution steps
        required_fields = ["reasoning", "execution_steps"]
        for field in required_fields:
            if field not in plan:
                return False
        
        # Execution steps should be a list
        if not isinstance(plan.get("execution_steps"), list):
            return False
        
        # Should have at least one execution step
        if len(plan.get("execution_steps", [])) == 0:
            return False
        
        return True

    def get_plan_summary(self, plan: dict) -> str:
        """
        Get a text summary of the query plan.
        
        Args:
            plan: The query plan dictionary
            
        Returns:
            A formatted string summary of the plan
        """
        if not self.validate_plan(plan):
            return "Invalid or incomplete query plan"
        
        summary = f"Query Plan Summary:\n"
        summary += f"Reasoning: {plan.get('reasoning', 'N/A')}\n\n"
        
        if 'execution_steps' in plan:
            summary += "Execution Steps:\n"
            for i, step in enumerate(plan['execution_steps'], 1):
                summary += f"{i}. {step}\n"
        
        return summary
