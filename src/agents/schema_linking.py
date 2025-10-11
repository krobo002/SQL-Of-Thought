from src.agents.base import BaseAgent
from src.llm.base import BaseLLM
import json
from src.prompts.agent_prompts import AgentPrompts
import os

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

        prompt = AgentPrompts.schema_linking_agent_prompt(schema_str=schema_str, question=question)
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


def main():
    # Path to the JSON file
    json_path = os.path.join(os.path.dirname(__file__), '..', 'row_store', 'integration', 'content.json')

    # Read and parse the JSON file
    with open(json_path, 'r') as f:
        db_schema = json.load(f)

    print("Loaded db_schema:", db_schema)

    