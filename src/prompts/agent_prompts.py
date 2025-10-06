from string import Template

class AgentPrompts:
    @staticmethod
    def schema_linking_agent_prompt(schema_str, question):
        prompt_template = Template(
        """
            You are a Schema Linking Agent in an NL2SQL framework.Return the relevant schema links for generating SQL query for the question.\n"

            Given:
                - A natural language question
                - Database schemas with columns, primary keys (PK), and foreign keys (FK)

            Cross-check your schema for:
                - Missing or incorrect FK-PK relationships and add them
                - Incomplete column selections (especially join keys)
                - Table alias mismatches
                - Linkage errors that would lead to incorrect joins or groupBy clauses

            Question: $question

            Table Schema: $table_schema

            Return the schema links in given format:

            Table: primary_key_col, foreign_key_col, col1, col2, ... all other columns in Table

            ONLY list relevant tables and columns and Foreign Keys in given format and no other extra characters.
        """)
        return prompt_template.substitute(table_schema=schema_str, question=question)