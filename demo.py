"""
SQL-of-Thought Pipeline Demo

This script demonstrates how to use the complete SQL-of-Thought framework
with all agents working together in the pipeline as described in the paper.
"""

import os
import sys
import json
import logging
from pathlib import Path

# Add src to path for imports
sys.path.append(str(Path(__file__).parent / "src"))

from src.core.pipeline import SQLOfThoughtPipeline
from src.llm.ollama_interface import OllamaInterface
from src.llm import LLMFactory
from src.database.execution_engine import create_spider_executor, DatabaseExecutorFactory
from src.error_taxonomy import SQLErrorTaxonomy


def setup_logging():
    """Setup logging configuration"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('sql_of_thought_demo.log'),
            logging.StreamHandler()
        ]
    )


def create_sample_schema():
    """Create a sample database schema for demonstration"""
    return {
        "tables": [
            {
                "name": "students",
                "columns": [
                    {"name": "student_id", "type": "INTEGER", "primary_key": True},
                    {"name": "name", "type": "TEXT"},
                    {"name": "age", "type": "INTEGER"},
                    {"name": "major", "type": "TEXT"},
                    {"name": "gpa", "type": "REAL"}
                ],
                "foreign_keys": []
            },
            {
                "name": "courses",
                "columns": [
                    {"name": "course_id", "type": "INTEGER", "primary_key": True},
                    {"name": "course_name", "type": "TEXT"},
                    {"name": "credits", "type": "INTEGER"},
                    {"name": "department", "type": "TEXT"}
                ],
                "foreign_keys": []
            },
            {
                "name": "enrollments",
                "columns": [
                    {"name": "enrollment_id", "type": "INTEGER", "primary_key": True},
                    {"name": "student_id", "type": "INTEGER"},
                    {"name": "course_id", "type": "INTEGER"},
                    {"name": "grade", "type": "TEXT"},
                    {"name": "semester", "type": "TEXT"}
                ],
                "foreign_keys": [
                    {"column": "student_id", "referenced_table": "students", "referenced_column": "student_id"},
                    {"column": "course_id", "referenced_table": "courses", "referenced_column": "course_id"}
                ]
            }
        ]
    }


def demo_error_taxonomy():
    """Demonstrate the error taxonomy system"""
    print("\n=== SQL Error Taxonomy Demo ===")
    
    taxonomy = SQLErrorTaxonomy()
    
    print("Error Categories:")
    for category in taxonomy.ErrorCategory:
        errors = taxonomy.get_errors_by_category(category)
        print(f"\n{category.value}: ({len(errors)} errors)")
        for error in errors[:3]:  # Show first 3 errors in each category
            print(f"  - {error.code}: {error.description}")
        if len(errors) > 3:
            print(f"  ... and {len(errors) - 3} more")
    
    print(f"\nTotal error types: {len(taxonomy.get_all_error_codes())}")


def demo_llm_interfaces():
    """Demonstrate different LLM interfaces"""
    print("\n=== LLM Interfaces Demo ===")
    
    # Check available LLM interfaces
    interfaces = []
    
    # Try Ollama (local LLM - primary choice)
    try:
        ollama_llm = LLMFactory.create_ollama(model="llama3.2")
        interfaces.append(("Ollama Llama3.2", ollama_llm))
        print("✓ Ollama Llama3.2 available (local inference, no API key required)")
    except Exception as e:
        print(f"✗ Ollama Llama3.2 unavailable: {str(e)}")
        print("  Hint: Make sure Ollama is running with 'ollama serve' and model is pulled with 'ollama pull llama3.2'")
    
    # Try alternative Ollama models
    for model_name in ["llama3.1", "llama2", "mistral", "codellama"]:
        try:
            ollama_llm = LLMFactory.create_ollama(model=model_name)
            interfaces.append((f"Ollama {model_name}", ollama_llm))
            print(f"✓ Ollama {model_name} available as fallback")
            break  # Use first available model as fallback
        except Exception:
            continue
    
    # If no Ollama models work, show how to set them up
    if not interfaces:
        print("\n⚠️  No Ollama models available. To use local LLMs:")
        print("   1. Install Ollama: https://ollama.ai")
        print("   2. Start Ollama: ollama serve")
        print("   3. Pull a model: ollama pull llama3.2")
        print("   4. Run this demo again")
        
        # For backward compatibility, you can still use cloud providers:
        print("\n   Alternative: Set ANTHROPIC_API_KEY or OPENAI_API_KEY for cloud LLMs")
    
    return interfaces


def demo_pipeline_execution(llm_interface, llm_name):
    """Demonstrate complete pipeline execution"""
    print(f"\n=== Pipeline Execution Demo with {llm_name} ===")
    
    # Create pipeline
    pipeline = SQLOfThoughtPipeline(
        llm=llm_interface,
        max_correction_attempts=3,
        enable_cost_tracking=True,
        enable_detailed_logging=True
    )
    
    # Sample question and schema
    question = "What are the names of students who have enrolled in Computer Science courses?"
    schema = create_sample_schema()
    
    print(f"Question: {question}")
    print(f"Schema: {len(schema['tables'])} tables (students, courses, enrollments)")
    
    # Execute pipeline without database (just SQL generation)
    print("\nExecuting SQL-of-Thought pipeline...")
    result = pipeline.execute(question, schema, db_executor=None)
    
    # Display results
    print(f"\nPipeline Results:")
    print(f"Success: {result.success}")
    print(f"Final SQL: {result.final_sql}")
    print(f"Execution Steps: {len(result.execution_steps)}")
    print(f"Correction Attempts: {result.correction_attempts}")
    print(f"Total Time: {result.total_time:.2f}s")
    print(f"Estimated Cost: ${result.cost_estimate:.4f}")
    
    if result.error_message:
        print(f"Error: {result.error_message}")
    
    # Show execution steps
    print("\nExecution Steps:")
    for i, step in enumerate(result.execution_steps, 1):
        status = "✓" if step['success'] else "✗"
        print(f"  {i}. {status} {step['agent']} ({step['execution_time']:.2f}s)")
        if not step['success'] and 'error_message' in step:
            print(f"     Error: {step['error_message']}")
    
    # Show pipeline summary
    summary = pipeline.get_pipeline_summary()
    print(f"\nPipeline Summary:")
    print(f"  Total Steps: {summary['total_steps']}")
    print(f"  Successful: {summary['successful_steps']}")
    print(f"  Failed: {summary['failed_steps']}")
    print(f"  Agents Used: {', '.join(summary['agents_used'])}")
    
    return result


def demo_database_execution():
    """Demonstrate database execution capabilities"""
    print("\n=== Database Execution Demo ===")
    
    # This would require actual Spider database files
    # For now, just show the interface
    
    print("Database Executor Types Available:")
    print("  - SQLiteExecutor (for Spider dataset)")
    print("  - MySQLExecutor (for MySQL databases)")
    
    try:
        # Try to create a SQLite executor (will fail without actual DB file)
        db_path = "./data/databases/sample.db"
        if Path(db_path).exists():
            executor = create_spider_executor(db_path)
            print(f"✓ SQLite executor created for {db_path}")
            
            # Get schema info
            schema_info = executor.get_schema_info()
            print(f"  Tables: {len(schema_info.get('tables', []))}")
        else:
            print(f"✗ SQLite database not found at {db_path}")
    except Exception as e:
        print(f"✗ Failed to create SQLite executor: {str(e)}")


def demo_individual_agents(llm_interface, llm_name):
    """Demonstrate individual agent capabilities"""
    print(f"\n=== Individual Agents Demo with {llm_name} ===")
    
    question = "Show me the top 5 students with highest GPA in Computer Science major"
    schema = create_sample_schema()
    
    try:
        # Schema Linking Agent
        from src.agents.schema_linking import SchemaLinkingAgent
        schema_agent = SchemaLinkingAgent(llm_interface)
        print("Testing Schema Linking Agent...")
        schema_result = schema_agent.execute(question, schema)
        print(f"✓ Schema linking result: {type(schema_result)}")
        
        # Subproblem Agent
        from src.agents.subproblem import SubproblemAgent
        subproblem_agent = SubproblemAgent(llm_interface)
        print("Testing Subproblem Agent...")
        subproblem_result = subproblem_agent.execute(question, schema_result)
        print(f"✓ Subproblem result: {len(subproblem_result)} clauses identified")
        
        # Query Plan Agent
        from src.agents.query_plan import QueryPlanAgent
        plan_agent = QueryPlanAgent(llm_interface)
        print("Testing Query Plan Agent...")
        plan_result = plan_agent.execute(question, schema_result, subproblem_result)
        print(f"✓ Query plan result: {len(plan_result.get('execution_steps', []))} steps")
        
        # SQL Generation Agent
        from src.agents.sql_generation import SQLGenerationAgent
        sql_agent = SQLGenerationAgent(llm_interface)
        print("Testing SQL Generation Agent...")
        sql_result = sql_agent.execute(question, plan_result, schema_result)
        print(f"✓ SQL generated: {sql_result.get('is_valid', False)} (valid)")
        print(f"  SQL: {sql_result.get('sql', 'N/A')[:100]}...")
        
    except Exception as e:
        print(f"✗ Agent testing failed: {str(e)}")


def main():
    """Main demo function"""
    print("SQL-of-Thought Framework Demo")
    print("=" * 50)
    print("This demo showcases the complete implementation of the")
    print("SQL-of-Thought paper: 'Multi-agentic Text-to-SQL with Guided Error Correction'")
    print()
    
    setup_logging()
    
    # Demo error taxonomy
    demo_error_taxonomy()
    
    # Demo LLM interfaces
    available_llms = demo_llm_interfaces()
    
    if not available_llms:
        print("\n❌ No LLM interfaces available!")
        print("Please set ANTHROPIC_API_KEY or OPENAI_API_KEY environment variables.")
        return
    
    # Demo database execution
    demo_database_execution()
    
    # Demo with each available LLM
    for llm_name, llm_interface in available_llms:
        try:
            # Demo individual agents
            demo_individual_agents(llm_interface, llm_name)
            
            # Demo complete pipeline
            result = demo_pipeline_execution(llm_interface, llm_name)
            
            if result.success:
                print(f"✓ {llm_name} pipeline completed successfully!")
            else:
                print(f"✗ {llm_name} pipeline failed: {result.error_message}")
                
        except Exception as e:
            print(f"✗ Demo failed with {llm_name}: {str(e)}")
    
    print("\n" + "=" * 50)
    print("Demo completed!")
    print("\nTo use SQL-of-Thought in your project:")
    print("1. Install and run Ollama for local LLM inference:")
    print("   - Download from https://ollama.ai")
    print("   - Run: ollama serve")
    print("   - Pull model: ollama pull llama3.2")
    print("2. Install required dependencies: pip install -r requirements.txt")
    print("3. Import and use the SQLOfThoughtPipeline class")
    print("4. For evaluation, provide Spider database files")
    print("\nOllama provides free local inference without API keys!")


if __name__ == "__main__":
    main()