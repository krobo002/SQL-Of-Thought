"""
SQL-of-Thought Pipeline Implementation

This module implements the main pipeline that orchestrates all agents in the SQL-of-Thought
framework according to the architecture described in the paper.
"""

import time
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
import logging

from src.agents.schema_linking import SchemaLinkingAgent
from src.agents.subproblem import SubproblemAgent
from src.agents.query_plan import QueryPlanAgent
from src.agents.sql_generation import SQLGenerationAgent
from src.agents.correction_plan import CorrectionPlanAgent
from src.agents.correction_sql import CorrectionSQLAgent
from src.error_taxonomy import SQLErrorTaxonomy
from src.llm.base import BaseLLM


@dataclass
class PipelineResult:
    """Result from the SQL-of-Thought pipeline execution"""
    success: bool
    final_sql: str
    execution_steps: List[Dict]
    correction_attempts: int
    total_time: float
    cost_estimate: float
    error_message: Optional[str] = None
    
    def to_dict(self):
        return asdict(self)


@dataclass
class ExecutionStep:
    """Individual step in the pipeline execution"""
    agent: str
    input_data: Dict
    output_data: Dict
    execution_time: float
    success: bool
    error_message: Optional[str] = None


class SQLOfThoughtPipeline:
    """
    Main pipeline class for the SQL-of-Thought framework.
    
    This pipeline orchestrates all agents in the correct sequence:
    1. Schema Linking Agent
    2. Subproblem Agent  
    3. Query Plan Agent
    4. SQL Generation Agent
    5. Database Execution
    6. Guided Correction Loop (if needed)
       - Correction Plan Agent
       - Correction SQL Agent
       - Re-execution
    """
    
    def __init__(self, 
                 llm: BaseLLM,
                 max_correction_attempts: int = 3,
                 enable_cost_tracking: bool = True,
                 enable_detailed_logging: bool = True):
        """
        Initialize the SQL-of-Thought pipeline.
        
        Args:
            llm: The language model interface to use
            max_correction_attempts: Maximum number of correction attempts
            enable_cost_tracking: Whether to track API costs
            enable_detailed_logging: Whether to enable detailed logging
        """
        self.llm = llm
        self.max_correction_attempts = max_correction_attempts
        self.enable_cost_tracking = enable_cost_tracking
        self.enable_detailed_logging = enable_detailed_logging
        
        # Initialize agents
        self.schema_linking_agent = SchemaLinkingAgent(llm)
        self.subproblem_agent = SubproblemAgent(llm)
        self.query_plan_agent = QueryPlanAgent(llm)
        self.sql_generation_agent = SQLGenerationAgent(llm)
        self.correction_plan_agent = CorrectionPlanAgent(llm)
        self.correction_sql_agent = CorrectionSQLAgent(llm)
        
        # Initialize error taxonomy
        self.error_taxonomy = SQLErrorTaxonomy()
        
        # Setup logging
        self.logger = logging.getLogger(__name__)
        if enable_detailed_logging:
            self.logger.setLevel(logging.INFO)
        
        # Cost tracking
        self.total_cost = 0.0
        self.execution_steps = []

    def execute(self, 
                question: str, 
                db_schema: Dict,
                db_executor=None) -> PipelineResult:
        """
        Execute the complete SQL-of-Thought pipeline.
        
        Args:
            question: Natural language question
            db_schema: Database schema information
            db_executor: Database executor for running SQL queries
            
        Returns:
            PipelineResult containing the final SQL and execution details
        """
        start_time = time.time()
        self.execution_steps = []
        self.total_cost = 0.0
        
        try:
            # Step 1: Schema Linking
            schema_result = self._execute_schema_linking(question, db_schema)
            if not schema_result['success']:
                return self._create_failure_result(
                    "Schema linking failed", 
                    schema_result.get('error_message', 'Unknown error'),
                    start_time
                )
            
            # Step 2: Subproblem Identification
            subproblem_result = self._execute_subproblem_identification(
                question, schema_result['output']
            )
            if not subproblem_result['success']:
                return self._create_failure_result(
                    "Subproblem identification failed",
                    subproblem_result.get('error_message', 'Unknown error'),
                    start_time
                )
            
            # Step 3: Query Plan Generation
            query_plan_result = self._execute_query_planning(
                question, schema_result['output'], subproblem_result['output']
            )
            if not query_plan_result['success']:
                return self._create_failure_result(
                    "Query planning failed",
                    query_plan_result.get('error_message', 'Unknown error'),
                    start_time
                )
            
            # Step 4: SQL Generation
            sql_result = self._execute_sql_generation(
                question, query_plan_result['output'], schema_result['output']
            )
            if not sql_result['success']:
                return self._create_failure_result(
                    "SQL generation failed",
                    sql_result.get('error_message', 'Unknown error'),
                    start_time
                )
            
            current_sql = sql_result['output']['sql']
            
            # Step 5: Database Execution and Correction Loop
            if db_executor:
                final_sql, correction_attempts = self._execute_with_correction_loop(
                    question=question,
                    schema_links=schema_result['output'],
                    initial_sql=current_sql,
                    query_plan=query_plan_result['output'],
                    db_executor=db_executor
                )
            else:
                final_sql = current_sql
                correction_attempts = 0
                self.logger.warning("No database executor provided - skipping execution and correction")
            
            # Create successful result
            total_time = time.time() - start_time
            return PipelineResult(
                success=True,
                final_sql=final_sql,
                execution_steps=self.execution_steps,
                correction_attempts=correction_attempts,
                total_time=total_time,
                cost_estimate=self.total_cost
            )
            
        except Exception as e:
            self.logger.error(f"Pipeline execution failed: {str(e)}")
            return self._create_failure_result(
                "Pipeline execution failed",
                str(e),
                start_time
            )

    def _execute_schema_linking(self, question: str, db_schema: Dict) -> Dict:
        """Execute the Schema Linking Agent"""
        step_start = time.time()
        
        try:
            self.logger.info("Executing Schema Linking Agent")
            result = self.schema_linking_agent.execute(question, db_schema)
            
            execution_time = time.time() - step_start
            self._track_cost("schema_linking", execution_time)
            
            step = ExecutionStep(
                agent="SchemaLinkingAgent",
                input_data={"question": question, "db_schema_keys": list(db_schema.keys())},
                output_data=result,
                execution_time=execution_time,
                success=True
            )
            self.execution_steps.append(asdict(step))
            
            return {
                'success': True,
                'output': result,
                'execution_time': execution_time
            }
            
        except Exception as e:
            execution_time = time.time() - step_start
            error_msg = f"Schema linking failed: {str(e)}"
            self.logger.error(error_msg)
            
            step = ExecutionStep(
                agent="SchemaLinkingAgent",
                input_data={"question": question},
                output_data={},
                execution_time=execution_time,
                success=False,
                error_message=error_msg
            )
            self.execution_steps.append(asdict(step))
            
            return {
                'success': False,
                'error_message': error_msg,
                'execution_time': execution_time
            }

    def _execute_subproblem_identification(self, question: str, schema_links: Dict) -> Dict:
        """Execute the Subproblem Agent"""
        step_start = time.time()
        
        try:
            self.logger.info("Executing Subproblem Agent")
            result = self.subproblem_agent.execute(question, schema_links)
            
            execution_time = time.time() - step_start
            self._track_cost("subproblem", execution_time)
            
            step = ExecutionStep(
                agent="SubproblemAgent",
                input_data={"question": question, "schema_links": schema_links},
                output_data=result,
                execution_time=execution_time,
                success=True
            )
            self.execution_steps.append(asdict(step))
            
            return {
                'success': True,
                'output': result,
                'execution_time': execution_time
            }
            
        except Exception as e:
            execution_time = time.time() - step_start
            error_msg = f"Subproblem identification failed: {str(e)}"
            self.logger.error(error_msg)
            
            step = ExecutionStep(
                agent="SubproblemAgent",
                input_data={"question": question},
                output_data={},
                execution_time=execution_time,
                success=False,
                error_message=error_msg
            )
            self.execution_steps.append(asdict(step))
            
            return {
                'success': False,
                'error_message': error_msg,
                'execution_time': execution_time
            }

    def _execute_query_planning(self, question: str, schema_links: Dict, subproblems: Dict) -> Dict:
        """Execute the Query Plan Agent"""
        step_start = time.time()
        
        try:
            self.logger.info("Executing Query Plan Agent")
            result = self.query_plan_agent.execute(question, schema_links, subproblems)
            
            execution_time = time.time() - step_start
            self._track_cost("query_planning", execution_time)
            
            step = ExecutionStep(
                agent="QueryPlanAgent",
                input_data={
                    "question": question, 
                    "schema_links": schema_links,
                    "subproblems": subproblems
                },
                output_data=result,
                execution_time=execution_time,
                success=True
            )
            self.execution_steps.append(asdict(step))
            
            return {
                'success': True,
                'output': result,
                'execution_time': execution_time
            }
            
        except Exception as e:
            execution_time = time.time() - step_start
            error_msg = f"Query planning failed: {str(e)}"
            self.logger.error(error_msg)
            
            step = ExecutionStep(
                agent="QueryPlanAgent",
                input_data={"question": question},
                output_data={},
                execution_time=execution_time,
                success=False,
                error_message=error_msg
            )
            self.execution_steps.append(asdict(step))
            
            return {
                'success': False,
                'error_message': error_msg,
                'execution_time': execution_time
            }

    def _execute_sql_generation(self, question: str, query_plan: Dict, schema_links: Dict) -> Dict:
        """Execute the SQL Generation Agent"""
        step_start = time.time()
        
        try:
            self.logger.info("Executing SQL Generation Agent")
            result = self.sql_generation_agent.execute(question, query_plan, schema_links)
            
            execution_time = time.time() - step_start
            self._track_cost("sql_generation", execution_time)
            
            step = ExecutionStep(
                agent="SQLGenerationAgent",
                input_data={
                    "question": question,
                    "query_plan": query_plan,
                    "schema_links": schema_links
                },
                output_data=result,
                execution_time=execution_time,
                success=True
            )
            self.execution_steps.append(asdict(step))
            
            return {
                'success': True,
                'output': result,
                'execution_time': execution_time
            }
            
        except Exception as e:
            execution_time = time.time() - step_start
            error_msg = f"SQL generation failed: {str(e)}"
            self.logger.error(error_msg)
            
            step = ExecutionStep(
                agent="SQLGenerationAgent",
                input_data={"question": question},
                output_data={},
                execution_time=execution_time,
                success=False,
                error_message=error_msg
            )
            self.execution_steps.append(asdict(step))
            
            return {
                'success': False,
                'error_message': error_msg,
                'execution_time': execution_time
            }

    def _execute_with_correction_loop(self, 
                                    question: str,
                                    schema_links: Dict,
                                    initial_sql: str,
                                    query_plan: Dict,
                                    db_executor) -> Tuple[str, int]:
        """
        Execute SQL with guided correction loop.
        
        Returns:
            Tuple of (final_sql, correction_attempts)
        """
        current_sql = initial_sql
        correction_attempts = 0
        
        while correction_attempts <= self.max_correction_attempts:
            # Try to execute the current SQL
            execution_result = self._execute_sql_on_database(current_sql, db_executor)
            
            if execution_result['success']:
                self.logger.info(f"SQL executed successfully after {correction_attempts} correction attempts")
                return current_sql, correction_attempts
            
            # If we've reached max attempts, return the last SQL
            if correction_attempts >= self.max_correction_attempts:
                self.logger.warning(f"Max correction attempts ({self.max_correction_attempts}) reached")
                return current_sql, correction_attempts
            
            # Generate correction plan
            correction_plan_result = self._execute_correction_planning(
                question=question,
                schema_links=schema_links,
                failed_sql=current_sql,
                execution_error=execution_result['error_message'],
                query_plan=query_plan
            )
            
            if not correction_plan_result['success']:
                self.logger.error("Correction planning failed")
                return current_sql, correction_attempts
            
            # Generate corrected SQL
            correction_sql_result = self._execute_sql_correction(
                question=question,
                schema_links=schema_links,
                failed_sql=current_sql,
                correction_plan=correction_plan_result['output'],
                query_plan=query_plan
            )
            
            if not correction_sql_result['success']:
                self.logger.error("SQL correction failed")
                return current_sql, correction_attempts
            
            # Update current SQL and increment attempts
            current_sql = correction_sql_result['output']['sql']
            correction_attempts += 1
            
            self.logger.info(f"Correction attempt #{correction_attempts} completed")
        
        return current_sql, correction_attempts

    def _execute_sql_on_database(self, sql: str, db_executor) -> Dict:
        """Execute SQL on database and return results"""
        try:
            # This is a placeholder - actual implementation would depend on db_executor interface
            result = db_executor.execute(sql)
            return {
                'success': True,
                'result': result,
                'execution_time': 0.1  # Placeholder
            }
        except Exception as e:
            return {
                'success': False,
                'error_message': str(e),
                'execution_time': 0.1  # Placeholder
            }

    def _execute_correction_planning(self, question: str, schema_links: Dict, 
                                   failed_sql: str, execution_error: str, 
                                   query_plan: Dict) -> Dict:
        """Execute the Correction Plan Agent"""
        step_start = time.time()
        
        try:
            self.logger.info("Executing Correction Plan Agent")
            result = self.correction_plan_agent.execute(
                question=question,
                schema_links=schema_links,
                failed_sql=failed_sql,
                execution_error=execution_error,
                query_plan=query_plan
            )
            
            execution_time = time.time() - step_start
            self._track_cost("correction_planning", execution_time)
            
            step = ExecutionStep(
                agent="CorrectionPlanAgent",
                input_data={
                    "question": question,
                    "failed_sql": failed_sql,
                    "execution_error": execution_error
                },
                output_data=result,
                execution_time=execution_time,
                success=True
            )
            self.execution_steps.append(asdict(step))
            
            return {
                'success': True,
                'output': result,
                'execution_time': execution_time
            }
            
        except Exception as e:
            execution_time = time.time() - step_start
            error_msg = f"Correction planning failed: {str(e)}"
            self.logger.error(error_msg)
            
            step = ExecutionStep(
                agent="CorrectionPlanAgent",
                input_data={"question": question},
                output_data={},
                execution_time=execution_time,
                success=False,
                error_message=error_msg
            )
            self.execution_steps.append(asdict(step))
            
            return {
                'success': False,
                'error_message': error_msg,
                'execution_time': execution_time
            }

    def _execute_sql_correction(self, question: str, schema_links: Dict,
                              failed_sql: str, correction_plan: Dict,
                              query_plan: Dict) -> Dict:
        """Execute the Correction SQL Agent"""
        step_start = time.time()
        
        try:
            self.logger.info("Executing Correction SQL Agent")
            result = self.correction_sql_agent.execute(
                question=question,
                schema_links=schema_links,
                failed_sql=failed_sql,
                correction_plan=correction_plan,
                query_plan=query_plan
            )
            
            execution_time = time.time() - step_start
            self._track_cost("sql_correction", execution_time)
            
            step = ExecutionStep(
                agent="CorrectionSQLAgent",
                input_data={
                    "question": question,
                    "failed_sql": failed_sql,
                    "correction_plan": correction_plan
                },
                output_data=result,
                execution_time=execution_time,
                success=True
            )
            self.execution_steps.append(asdict(step))
            
            return {
                'success': True,
                'output': result,
                'execution_time': execution_time
            }
            
        except Exception as e:
            execution_time = time.time() - step_start
            error_msg = f"SQL correction failed: {str(e)}"
            self.logger.error(error_msg)
            
            step = ExecutionStep(
                agent="CorrectionSQLAgent",
                input_data={"question": question},
                output_data={},
                execution_time=execution_time,
                success=False,
                error_message=error_msg
            )
            self.execution_steps.append(asdict(step))
            
            return {
                'success': False,
                'error_message': error_msg,
                'execution_time': execution_time
            }

    def _track_cost(self, operation: str, execution_time: float):
        """Track API costs (placeholder implementation)"""
        if not self.enable_cost_tracking:
            return
        
        # Rough cost estimation based on operation type and time
        # This would need to be refined based on actual LLM pricing
        cost_per_operation = {
            "schema_linking": 0.01,
            "subproblem": 0.01,
            "query_planning": 0.02,
            "sql_generation": 0.01,
            "correction_planning": 0.02,
            "sql_correction": 0.01
        }
        
        estimated_cost = cost_per_operation.get(operation, 0.01)
        self.total_cost += estimated_cost

    def _create_failure_result(self, error_type: str, error_message: str, start_time: float) -> PipelineResult:
        """Create a failure result"""
        total_time = time.time() - start_time
        return PipelineResult(
            success=False,
            final_sql="",
            execution_steps=self.execution_steps,
            correction_attempts=0,
            total_time=total_time,
            cost_estimate=self.total_cost,
            error_message=f"{error_type}: {error_message}"
        )

    def get_pipeline_summary(self) -> Dict:
        """Get a summary of the pipeline execution"""
        if not self.execution_steps:
            return {"status": "No execution steps recorded"}
        
        summary = {
            "total_steps": len(self.execution_steps),
            "successful_steps": sum(1 for step in self.execution_steps if step['success']),
            "failed_steps": sum(1 for step in self.execution_steps if not step['success']),
            "total_time": sum(step['execution_time'] for step in self.execution_steps),
            "total_cost": self.total_cost,
            "agents_used": [step['agent'] for step in self.execution_steps]
        }
        
        return summary
