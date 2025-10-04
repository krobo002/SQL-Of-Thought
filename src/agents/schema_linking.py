from src.agents.base import BaseAgent
from src.llm.base import BaseLLM
import json

class SchemaLinkingAgent(BaseAgent):
    """
    Agent for linking natural language questions to database schema.
    """

    def __init__(self, llm: BaseLLM):
        super().__init__(llm)

    def execute(self, question: str, db_schema: dict) -> dict:
        """
        Identifies relevant tables, columns, and relationships from the schema.

        Args:
            question: The natural language question.
            db_schema: A dictionary representing the database schema.

        Returns:
            A dictionary containing the linked schema information.
        """
        prompt = self._create_prompt(question, db_schema)
        response = self.llm.predict(prompt)
        return self._parse_response(response)

    def _create_prompt(self, question: str, db_schema: dict) -> str:
        """
        Creates the prompt for the LLM.
        """
        # Simplified schema representation for the prompt
        schema_representation = []
        for table in db_schema.get('tables', []):
            table_name = table.get('name')
            columns = [col.get('name') for col in table.get('columns', [])]
            schema_representation.append(f"Table {table_name}: {', '.join(columns)}")

        schema_str = "\n".join(schema_representation)

        prompt = f"""
Given the following database schema:
{schema_str}

And the natural language question:
"{question}"

Identify the relevant tables and columns for answering this question.
Also, identify any primary keys, foreign keys, and join relationships that might be needed.

Please provide the output in a JSON format with the following keys:
- "tables": A list of relevant table names.
- "columns": A list of relevant column names.
- "relationships": A list of strings describing join relationships (e.g., "table1.column1 = table2.column2").

Example output:
{{
  "tables": ["employees", "departments"],
  "columns": ["employees.name", "departments.name", "employees.department_id"],
  "relationships": ["employees.department_id = departments.id"]
}}
"""
        return prompt

    def _parse_response(self, response: str) -> dict:
        """
        Parses the LLM's JSON response.
        """
        try:
            # The response might contain markdown code block syntax
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0]
            return json.loads(response)
        except (json.JSONDecodeError, IndexError) as e:
            # Handle cases where the response is not valid JSON
            # Or when splitting the string fails
            print(f"Error parsing LLM response: {e}")
            return {
                "tables": [],
                "columns": [],
                "relationships": []
            }
