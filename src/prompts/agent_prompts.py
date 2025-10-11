from string import Template

class AgentPrompts:
    @staticmethod
    def schema_linking_agent_prompt(schema_str, question):
        """Schema Linking Agent prompt template"""
        prompt_template = Template(
        """
            You are a Schema Linking Agent in an NL2SQL framework. Return the relevant schema links for generating SQL query for the question.

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

    @staticmethod
    def subproblem_agent_prompt(question, schema_links):
        """Subproblem Agent prompt template"""
        prompt_template = Template(
        """
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

        Question: $question

        Schema Links: $schema_links

        For each applicable clause, provide:
        1. The clause type
        2. A brief description of what needs to be done
        3. The relevant columns/tables involved
        4. Any specific conditions or requirements

        Return your analysis as a JSON object with clause types as keys and their requirements as values.

        Example format:
        {
            "SELECT": "Retrieve customer names and total order amounts",
            "FROM": "customers and orders tables",
            "JOIN": "Connect customers to orders via customer_id",
            "WHERE": "Filter for orders in the last year",
            "GROUP BY": "Group by customer to calculate totals",
            "ORDER BY": "Sort by total amount descending",
            "LIMIT": "Top 10 customers only"
        }

        JSON Response:
        """)
        return prompt_template.substitute(question=question, schema_links=schema_links)

    @staticmethod
    def query_plan_agent_prompt(question, schema_links, subproblems):
        """Query Plan Agent Chain-of-Thought prompt template"""
        prompt_template = Template(
        """
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

        Question: $question

        Schema Links: $schema_links

        Subproblems: $subproblems

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
        {
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
        }

        JSON Response:
        """)
        return prompt_template.substitute(question=question, schema_links=schema_links, subproblems=subproblems)

    @staticmethod
    def sql_generation_agent_prompt(question, query_plan, schema_links):
        """SQL Generation Agent prompt template"""
        prompt_template = Template(
        """
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

        Question: $question

        Query Plan: $query_plan

        Schema Information: $schema_links

        Instructions:
        - Generate ONLY the SQL query
        - Use proper SQL syntax (SQLite compatible)
        - Include appropriate JOINs, WHERE conditions, GROUP BY, ORDER BY, LIMIT as specified in the plan
        - Use correct table and column names exactly as shown in the schema
        - Do not include explanations or comments in the SQL
        - Do not add trailing semicolons or extra formatting

        SQL Query:
        """)
        return prompt_template.substitute(question=question, query_plan=query_plan, schema_links=schema_links)

    @staticmethod
    def correction_plan_agent_prompt(question, schema_links, failed_sql, execution_error, query_plan, error_taxonomy):
        """Correction Plan Agent Chain-of-Thought prompt template"""
        prompt_template = Template(
        """
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

        Question: $question

        Schema Information: $schema_links

        Query Plan: $query_plan

        Failed SQL Query: $failed_sql

        Execution Error: $execution_error

        Error Taxonomy Reference:
        $error_taxonomy

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
        {
            "error_analysis": "Detailed analysis of what went wrong",
            "identified_errors": [
                {
                    "error_code": "error_code_from_taxonomy",
                    "category": "Error category",
                    "description": "What the error is",
                    "location": "Where in the query the error occurs"
                }
            ],
            "root_causes": [
                "Primary cause 1",
                "Secondary cause 2"
            ],
            "correction_steps": [
                {
                    "step": 1,
                    "action": "What to fix",
                    "reasoning": "Why this fix is needed",
                    "priority": "high/medium/low"
                }
            ],
            "expected_outcome": "What the corrected query should achieve",
            "alternative_approaches": ["Alternative approach 1", "Alternative approach 2"],
            "validation_checks": ["Check 1", "Check 2"]
        }

        JSON Response:
        """)
        return prompt_template.substitute(
            question=question, 
            schema_links=schema_links, 
            failed_sql=failed_sql, 
            execution_error=execution_error,
            query_plan=query_plan,
            error_taxonomy=error_taxonomy
        )

    @staticmethod
    def correction_sql_agent_prompt(question, schema_links, failed_sql, correction_plan, query_plan):
        """Correction SQL Agent prompt template"""
        prompt_template = Template(
        """
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

        Question: $question

        Schema Information: $schema_links

        Original Query Plan: $query_plan

        Failed SQL Query: $failed_sql

        Correction Plan: $correction_plan

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
        """)
        return prompt_template.substitute(
            question=question,
            schema_links=schema_links,
            failed_sql=failed_sql,
            correction_plan=correction_plan,
            query_plan=query_plan
        )