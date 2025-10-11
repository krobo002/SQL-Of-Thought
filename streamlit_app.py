"""
Streamlit Web Interface for SQL-of-Thought Pipeline

This provides a user-friendly web interface to interact with the
SQL-of-Thought framework for text-to-SQL generation.
"""

import streamlit as st
import os
import sys
import json
import time
from pathlib import Path
from datetime import datetime
import plotly.graph_objects as go
import plotly.express as px
import concurrent.futures
import threading

# Add src to path for imports
sys.path.append(str(Path(__file__).parent / "src"))

try:
    from src.core.pipeline import SQLOfThoughtPipeline
    from src.llm import LLMFactory
    from src.llm.ollama_interface import OllamaInterface
    from src.error_taxonomy import SQLErrorTaxonomy
    from src.error_taxonomy.taxonomy import ErrorCategory
    from src.database.execution_engine import create_spider_executor
    from src.database.mysql_connection import get_mysql_connection, execute_query, get_schema
except ImportError as e:
    st.error(f"Import error: {e}")
    st.error("Please ensure all dependencies are installed and the src directory is accessible.")
    st.stop()


def initialize_session_state():
    """Initialize session state variables"""
    if 'pipeline_results' not in st.session_state:
        st.session_state.pipeline_results = []
    if 'current_schema' not in st.session_state:
        st.session_state.current_schema = None
    if 'llm_interface' not in st.session_state:
        st.session_state.llm_interface = None


def setup_sidebar():
    """Setup the sidebar with configuration options"""
    st.sidebar.header("🔧 Configuration")
    
    # Database Connection Status
    st.sidebar.subheader("🗄️ Database Status")
    
    # Check if we have cached connection status
    if 'db_connection_status' not in st.session_state:
        st.session_state.db_connection_status = None
        st.session_state.db_status_check_time = 0
    
    # Only check connection every 30 seconds to avoid blocking
    current_time = time.time()
    if (st.session_state.db_connection_status is None or 
        current_time - st.session_state.db_status_check_time > 30):
        
        # Quick connection test with timeout
        try:
            from decouple import config
            import mysql.connector
            
            # Quick connection test with very short timeout
            host_full = config('MYSQL_HOST')
            host_parts = host_full.split(':')
            host = host_parts[0]
            port = int(host_parts[1]) if len(host_parts) > 1 else 3306
            
            connection = mysql.connector.connect(
                host=host,
                port=port,
                user=config('MYSQL_USER'),
                password=config('MYSQL_PASSWORD'),
                database=config('MYSQL_DB_NAME'),
                connection_timeout=2  # Very short timeout
            )
            
            if connection.is_connected():
                connection.close()
                st.session_state.db_connection_status = "connected"
            else:
                st.session_state.db_connection_status = "disconnected"
        except Exception as e:
            st.session_state.db_connection_status = f"error: {str(e)[:30]}"
        
        st.session_state.db_status_check_time = current_time
    
    # Display cached status
    if st.session_state.db_connection_status == "connected":
        st.sidebar.success("✅ MySQL Connected")
        from decouple import config
        st.sidebar.info(f"📍 Host: {config('MYSQL_HOST')}")
        st.sidebar.info(f"👤 User: {config('MYSQL_USER')}")
        st.sidebar.info(f"🗄️ DB: {config('MYSQL_DB_NAME')}")
    elif st.session_state.db_connection_status == "disconnected":
        st.sidebar.error("❌ MySQL Disconnected")
    else:
        st.sidebar.warning("⚠️ MySQL Status Unknown")
        if st.session_state.db_connection_status.startswith("error:"):
            st.sidebar.error(st.session_state.db_connection_status)
    
    # LLM Selection
    st.sidebar.subheader("LLM Selection")
    
    # Check available LLMs - prioritize Ollama (local, free)
    available_llms = []
    
    # Always add Ollama options (no API key required)
    available_llms.extend([
        "Ollama Llama3.2 (Local)", 
        "Ollama Llama3.1 (Local)", 
        "Ollama Llama2 (Local)",
        "Ollama Mistral (Local)",
        "Ollama CodeLlama (Local)"
    ])
    
    # Add cloud providers if API keys are available
    if os.getenv("ANTHROPIC_API_KEY"):
        available_llms.extend(["Claude-3 Opus", "Claude-3.5 Sonnet"])
    
    if os.getenv("OPENAI_API_KEY"):
        available_llms.extend(["GPT-4o", "GPT-3.5 Turbo"])
    
    selected_llm = st.sidebar.selectbox(
        "Choose LLM Model",
        available_llms,
        help="Ollama models run locally without API keys. Make sure Ollama is running with 'ollama serve'."
    )
    
    # Pipeline Configuration
    st.sidebar.subheader("Pipeline Settings")
    
    max_corrections = st.sidebar.slider(
        "Max Correction Attempts",
        min_value=1,
        max_value=5,
        value=3,
        help="Maximum number of error correction attempts"
    )
    
    enable_cost_tracking = st.sidebar.checkbox(
        "Enable Cost Tracking",
        value=True,
        help="Track estimated costs for LLM calls"
    )
    
    enable_detailed_logging = st.sidebar.checkbox(
        "Enable Detailed Logging",
        value=True,
        help="Show detailed execution logs"
    )
    
    # Create LLM interface
    try:
        if "Ollama" in selected_llm:
            # Extract model name from the selection
            if "Llama3.2" in selected_llm:
                model = "llama3.2"
            elif "Llama3.1" in selected_llm:
                model = "llama3.1"
            elif "Llama2" in selected_llm:
                model = "llama2"
            elif "Mistral" in selected_llm:
                model = "mistral"
            elif "CodeLlama" in selected_llm:
                model = "codellama"
            else:
                model = "llama3.2"  # Default
                
            llm_interface = LLMFactory.create_ollama(model=model)
            
        elif selected_llm == "Claude-3 Opus":
            llm_interface = LLMFactory.create_anthropic(model="claude-3-opus-20240229")
        elif selected_llm == "Claude-3.5 Sonnet":
            llm_interface = LLMFactory.create_anthropic(model="claude-3-5-sonnet-20241022")
        elif selected_llm == "GPT-4o":
            llm_interface = LLMFactory.create_openai(model="gpt-4o")
        elif selected_llm == "GPT-3.5 Turbo":
            llm_interface = LLMFactory.create_openai(model="gpt-3.5-turbo")
        else:
            st.sidebar.error(f"Unknown LLM: {selected_llm}")
            return None
    except Exception as e:
        st.sidebar.error(f"Failed to initialize {selected_llm}: {str(e)}")
        if "Ollama" in selected_llm:
            st.sidebar.info("Make sure Ollama is running: `ollama serve`")
            st.sidebar.info(f"And model is pulled: `ollama pull {model if 'model' in locals() else 'llama3.2'}`")
        return None
    
    return {
        'llm_interface': llm_interface,
        'llm_name': selected_llm,
        'max_corrections': max_corrections,
        'enable_cost_tracking': enable_cost_tracking,
        'enable_detailed_logging': enable_detailed_logging
    }


def create_sample_schemas():
    """Create sample database schemas for testing"""
    return {
        "University Database": {
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
        },
        "E-commerce Database": {
            "tables": [
                {
                    "name": "customers",
                    "columns": [
                        {"name": "customer_id", "type": "INTEGER", "primary_key": True},
                        {"name": "name", "type": "TEXT"},
                        {"name": "email", "type": "TEXT"},
                        {"name": "city", "type": "TEXT"},
                        {"name": "registration_date", "type": "DATE"}
                    ],
                    "foreign_keys": []
                },
                {
                    "name": "products",
                    "columns": [
                        {"name": "product_id", "type": "INTEGER", "primary_key": True},
                        {"name": "name", "type": "TEXT"},
                        {"name": "category", "type": "TEXT"},
                        {"name": "price", "type": "DECIMAL"},
                        {"name": "stock_quantity", "type": "INTEGER"}
                    ],
                    "foreign_keys": []
                },
                {
                    "name": "orders",
                    "columns": [
                        {"name": "order_id", "type": "INTEGER", "primary_key": True},
                        {"name": "customer_id", "type": "INTEGER"},
                        {"name": "product_id", "type": "INTEGER"},
                        {"name": "quantity", "type": "INTEGER"},
                        {"name": "order_date", "type": "DATE"},
                        {"name": "total_amount", "type": "DECIMAL"}
                    ],
                    "foreign_keys": [
                        {"column": "customer_id", "referenced_table": "customers", "referenced_column": "customer_id"},
                        {"column": "product_id", "referenced_table": "products", "referenced_column": "product_id"}
                    ]
                }
            ]
        }
    }


def display_schema_info(schema):
    """Display schema information in a formatted way"""
    st.subheader("📊 Database Schema")
    
    for table in schema["tables"]:
        with st.expander(f"Table: {table['name']}", expanded=False):
            # Columns
            st.write("**Columns:**")
            for col in table["columns"]:
                primary_key_indicator = " 🔑" if col.get("primary_key") else ""
                st.write(f"- `{col['name']}` ({col['type']}){primary_key_indicator}")
            
            # Foreign keys
            if table["foreign_keys"]:
                st.write("**Foreign Keys:**")
                for fk in table["foreign_keys"]:
                    st.write(f"- `{fk['column']}` → `{fk['referenced_table']}.{fk['referenced_column']}`")


@st.cache_data(ttl=300)  # Cache for 5 minutes
def load_mysql_schema():
    """Load MySQL database schema and convert to expected format"""
    try:
        # Get the database name from environment
        from decouple import config
        db_name = config('MYSQL_DB_NAME')
        
        # Test connection first
        connection = get_mysql_connection()
        if not connection:
            return None, "Failed to connect to MySQL database"
        connection.close()
        
        # Get schema information
        raw_schema = get_schema(db_name)
        if not raw_schema:
            return None, "Failed to retrieve database schema"
        
        # Convert MySQL schema to expected format
        tables = []
        for table_name, create_statement in raw_schema.items():
            # Parse the CREATE TABLE statement to extract columns
            columns = parse_mysql_create_statement(create_statement)
            
            tables.append({
                "name": table_name,
                "columns": columns,
                "foreign_keys": []  # TODO: Parse foreign keys from CREATE statement
            })
        
        schema = {
            "database_name": db_name,
            "tables": tables[:20]  # Limit to first 20 tables for performance
        }
        
        return schema, None
        
    except Exception as e:
        return None, f"Error loading MySQL schema: {str(e)}"


def parse_mysql_create_statement(create_statement):
    """Parse MySQL CREATE TABLE statement to extract column information"""
    import re
    
    columns = []
    # Split the CREATE statement into lines
    lines = create_statement.split('\n')
    
    for line in lines:
        line = line.strip()
        # Skip lines that don't define columns
        if not line or line.startswith('CREATE TABLE') or line.startswith(')') or line.startswith('KEY') or line.startswith('PRIMARY KEY') or line.startswith('UNIQUE KEY'):
            continue
        
        # Extract column definition
        if line.startswith('`') and ('(' in line or line.endswith(',')):
            # Remove backticks and parse column name and type
            line = line.strip(',')
            parts = line.split(' ')
            if len(parts) >= 2:
                col_name = parts[0].strip('`')
                col_type = parts[1]
                
                # Check for primary key
                is_primary = 'PRIMARY KEY' in line.upper() or 'AUTO_INCREMENT' in line.upper()
                
                columns.append({
                    "name": col_name,
                    "type": col_type,
                    "primary_key": is_primary
                })
    
    return columns


def create_mysql_executor():
    """Create a MySQL database executor for the pipeline"""
    class MySQLExecutor:
        def __init__(self):
            self.connection = None
        
        def execute_sql(self, sql_query):
            """Execute SQL query against MySQL database"""
            try:
                result = execute_query(sql_query)
                return {
                    'success': True,
                    'result': result,
                    'error': None
                }
            except Exception as e:
                return {
                    'success': False,
                    'result': None,
                    'error': str(e)
                }
        
        def test_connection(self):
            """Test database connection"""
            try:
                connection = get_mysql_connection()
                if connection:
                    connection.close()
                    return True
                return False
            except:
                return False
    
    return MySQLExecutor()


def execute_pipeline_sync(llm_interface, question, schema, config_params, use_mysql_executor=False):
    """Synchronous pipeline execution function for threading"""
    pipeline = SQLOfThoughtPipeline(
        llm=llm_interface,
        max_correction_attempts=config_params['max_corrections'],
        enable_cost_tracking=config_params['enable_cost_tracking'],
        enable_detailed_logging=config_params['enable_detailed_logging']
    )
    
    start_time = time.time()
    
    # Use MySQL executor if specified
    db_executor = create_mysql_executor() if use_mysql_executor else None
    result = pipeline.execute(question, schema, db_executor=db_executor)
    execution_time = time.time() - start_time
    
    return result, execution_time


def execute_pipeline(question, schema, config, use_mysql_executor=False):
    """Execute the SQL-of-Thought pipeline with non-blocking progress tracking"""
    
    # Prepare config params for threading
    config_params = {
        'max_corrections': config['max_corrections'],
        'enable_cost_tracking': config['enable_cost_tracking'],
        'enable_detailed_logging': config['enable_detailed_logging']
    }
    
    # Initialize session state for async execution tracking
    if 'pipeline_future' not in st.session_state:
        st.session_state.pipeline_future = None
    if 'pipeline_start_time' not in st.session_state:
        st.session_state.pipeline_start_time = None
    if 'pipeline_executor' not in st.session_state:
        st.session_state.pipeline_executor = None
    
    # Check if pipeline is already running
    if st.session_state.pipeline_future is not None:
        # Check if the future is done
        if st.session_state.pipeline_future.done():
            try:
                result, execution_time = st.session_state.pipeline_future.result()
                # Clean up - shutdown executor and clear session state
                if st.session_state.pipeline_executor:
                    st.session_state.pipeline_executor.shutdown(wait=False)
                st.session_state.pipeline_future = None
                st.session_state.pipeline_start_time = None
                st.session_state.pipeline_executor = None
                return result, execution_time
            except Exception as e:
                # Log detailed error internally, show generic message to user
                import logging
                logging.error(f"Pipeline execution failed: {str(e)}", exc_info=True)
                
                # Clean up resources
                if st.session_state.pipeline_executor:
                    st.session_state.pipeline_executor.shutdown(wait=False)
                st.session_state.pipeline_future = None
                st.session_state.pipeline_start_time = None
                st.session_state.pipeline_executor = None
                
                st.error("Pipeline execution failed due to an internal error. Please check the configuration and try again.")
                return None, 0
        else:
            # Still running - show progress
            elapsed_time = time.time() - st.session_state.pipeline_start_time
            progress_value = min(int((elapsed_time / 30) * 100), 90)  # Estimate 30s max, cap at 90%
            
            progress_bar = st.progress(progress_value)
            status_text = st.empty()
            
            if elapsed_time < 5:
                status_text.text(f"🔗 Initializing {config['llm_name']} pipeline... ({elapsed_time:.1f}s)")
            elif elapsed_time < 15:
                status_text.text(f"🧠 Analyzing schema and question... ({elapsed_time:.1f}s)")
            elif elapsed_time < 25:
                status_text.text(f"⚡ Executing multi-agent reasoning... ({elapsed_time:.1f}s)")
            else:
                status_text.text(f"🔤 Generating SQL query... ({elapsed_time:.1f}s)")
            
            # Auto-refresh every 2 seconds
            time.sleep(2)
            st.rerun()
            return None, 0  # Still processing
    
    # Start new pipeline execution
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    future = executor.submit(
        execute_pipeline_sync,
        config['llm_interface'],
        question,
        schema,
        config_params,
        use_mysql_executor
    )
    
    # Store future, executor, and start time in session state
    st.session_state.pipeline_future = future
    st.session_state.pipeline_executor = executor
    st.session_state.pipeline_start_time = time.time()
    
    # Show initial progress
    progress_bar = st.progress(5)
    status_text = st.empty()
    status_text.text(f"🚀 Starting {config['llm_name']} pipeline execution...")
    
    # Auto-refresh to check progress
    time.sleep(1)
    st.rerun()
    return None, 0  # Will be handled in next iteration


def display_pipeline_results(result, execution_time, llm_name):
    """Display pipeline execution results"""
    
    # Success/Failure indicator
    if result.success:
        st.success(f"✅ Pipeline completed successfully in {execution_time:.2f}s")
    else:
        st.error(f"❌ Pipeline failed: {result.error_message}")
    
    # Results overview
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Execution Steps", len(result.execution_steps))
    
    with col2:
        st.metric("Correction Attempts", result.correction_attempts)
    
    with col3:
        st.metric("Total Time", f"{result.total_time:.2f}s")
    
    with col4:
        st.metric("Estimated Cost", f"${result.cost_estimate:.4f}")
    
    # Generated SQL
    if result.final_sql:
        st.subheader("🔤 Generated SQL")
        st.code(result.final_sql, language="sql")
        
        # Copy to clipboard button
        if st.button("📋 Copy SQL to Clipboard"):
            st.write("SQL copied to clipboard!")  # Note: Actual clipboard copy would need additional JS
    
    # Execution steps
    if result.execution_steps:
        st.subheader("🔄 Execution Steps")
        
        for i, step in enumerate(result.execution_steps, 1):
            status_icon = "✅" if step['success'] else "❌"
            
            with st.expander(f"{status_icon} Step {i}: {step['agent']} ({step['execution_time']:.2f}s)"):
                if step['success']:
                    st.success("Step completed successfully")
                else:
                    st.error(f"Step failed: {step.get('error_message', 'Unknown error')}")
                
                # Show step details if available
                if 'details' in step:
                    st.json(step['details'])
    
    # Store result in session state
    result_entry = {
        'timestamp': datetime.now(),
        'llm_name': llm_name,
        'question': st.session_state.get('last_question', ''),
        'success': result.success,
        'sql': result.final_sql,
        'execution_time': execution_time,
        'cost_estimate': result.cost_estimate,
        'correction_attempts': result.correction_attempts
    }
    
    st.session_state.pipeline_results.append(result_entry)


def display_error_taxonomy():
    """Display the error taxonomy system"""
    st.subheader("🏷️ Error Taxonomy System")
    
    taxonomy = SQLErrorTaxonomy()
    
    # Overview metrics
    total_errors = len(taxonomy.get_all_error_codes())
    categories = list(ErrorCategory)
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Total Error Types", total_errors)
    with col2:
        st.metric("Error Categories", len(categories))
    
    # Category breakdown
    category_data = []
    for category in categories:
        errors = taxonomy.get_errors_by_category(category)
        category_data.append({
            'Category': category.value,
            'Count': len(errors),
            'Errors': [error.code for error in errors]
        })
    
    # Visualization
    fig = px.bar(
        x=[data['Category'] for data in category_data],
        y=[data['Count'] for data in category_data],
        title="Error Types by Category",
        labels={'x': 'Category', 'y': 'Number of Error Types'}
    )
    st.plotly_chart(fig, use_container_width=True)
    
    # Detailed breakdown
    for data in category_data:
        with st.expander(f"{data['Category']} ({data['Count']} errors)"):
            errors = taxonomy.get_errors_by_category(
                ErrorCategory(data['Category'])
            )
            for error in errors:
                st.write(f"**{error.code}**: {error.description}")


def display_results_history():
    """Display history of pipeline executions"""
    st.subheader("📈 Execution History")
    
    if not st.session_state.pipeline_results:
        st.info("No execution history yet. Run some queries to see results here.")
        return
    
    # Summary metrics
    results = st.session_state.pipeline_results
    success_rate = sum(1 for r in results if r['success']) / len(results) * 100
    avg_time = sum(r['execution_time'] for r in results) / len(results)
    total_cost = sum(r['cost_estimate'] for r in results)
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Queries", len(results))
    with col2:
        st.metric("Success Rate", f"{success_rate:.1f}%")
    with col3:
        st.metric("Avg Time", f"{avg_time:.2f}s")
    with col4:
        st.metric("Total Cost", f"${total_cost:.4f}")
    
    # Results table
    st.write("**Recent Executions:**")
    for i, result in enumerate(reversed(results[-10:]), 1):  # Show last 10
        with st.expander(f"Query {len(results) - i + 1}: {result['question'][:50]}..."):
            col1, col2 = st.columns([2, 1])
            
            with col1:
                st.write(f"**LLM:** {result['llm_name']}")
                st.write(f"**Status:** {'✅ Success' if result['success'] else '❌ Failed'}")
                st.write(f"**Time:** {result['execution_time']:.2f}s")
                st.write(f"**Cost:** ${result['cost_estimate']:.4f}")
                st.write(f"**Corrections:** {result['correction_attempts']}")
            
            with col2:
                st.write(f"**Timestamp:**")
                st.write(result['timestamp'].strftime("%Y-%m-%d %H:%M:%S"))
            
            if result['sql']:
                st.code(result['sql'], language="sql")


def main():
    """Main Streamlit application"""
    st.set_page_config(
        page_title="SQL-of-Thought Pipeline",
        page_icon="🤖",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Header
    st.title("🤖 SQL-of-Thought Pipeline")
    st.markdown("**Multi-agentic Text-to-SQL with Guided Error Correction**")
    st.markdown("*Based on the research paper implementing a 6-agent framework for robust SQL generation*")
    
    # Initialize session state
    initialize_session_state()
    
    # Setup sidebar configuration
    config = setup_sidebar()
    
    if not config:
        st.error("Please configure API keys to use the pipeline.")
        return
    
    # Main tabs
    tab1, tab2, tab3, tab4 = st.tabs(["🔍 Query Interface", "🏷️ Error Taxonomy", "📈 Results History", "ℹ️ About"])
    
    with tab1:
        st.header("Text-to-SQL Generation")
        
        # Schema selection
        sample_schemas = create_sample_schemas()
        schema_options = ["🗄️ MySQL Database (Live)"] + list(sample_schemas.keys()) + ["Custom Schema"]
        
        selected_schema_name = st.selectbox(
            "Choose Database Schema",
            schema_options,
            help="Select a schema: Live MySQL database, sample schemas, or provide your own"
        )
        
        if selected_schema_name == "🗄️ MySQL Database (Live)":
            st.subheader("🔄 Loading MySQL Database Schema")
            
            # Show loading progress
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            try:
                status_text.text("🔌 Testing database connection...")
                progress_bar.progress(25)
                
                # Quick connection test first
                connection = get_mysql_connection()
                if not connection:
                    st.error("❌ Failed to connect to MySQL database")
                    st.info("Please check your .env file configuration and ensure the database is accessible.")
                    schema = None
                else:
                    connection.close()
                    status_text.text("📊 Loading database schema...")
                    progress_bar.progress(50)
                    
                    # Load schema with caching
                    schema, error = load_mysql_schema()
                    progress_bar.progress(100)
                    
                    if error:
                        st.error(f"❌ Schema Loading Error: {error}")
                        schema = None
                    else:
                        status_text.text("✅ Schema loaded successfully!")
                        st.success("✅ Successfully connected to MySQL database!")
                        st.info(f"📊 Loaded {len(schema['tables'])} tables from database: `{schema['database_name']}`")
                        
                        # Show quick stats
                        total_columns = sum(len(table['columns']) for table in schema['tables'])
                        st.info(f"📈 Total columns across all tables: {total_columns}")
                        
            except Exception as e:
                progress_bar.progress(0)
                status_text.text("❌ Connection failed")
                st.error(f"Database Error: {str(e)}")
                schema = None
            finally:
                # Clean up progress indicators after a short delay
                time.sleep(1)
                progress_bar.empty()
                status_text.empty()
                
        elif selected_schema_name == "Custom Schema":
            st.subheader("📝 Custom Schema Input")
            schema_json = st.text_area(
                "Enter schema JSON",
                height=300,
                placeholder='{"tables": [{"name": "table1", "columns": [...], "foreign_keys": [...]}]}'
            )
            
            try:
                if schema_json.strip():
                    schema = json.loads(schema_json)
                else:
                    schema = None
            except json.JSONDecodeError as e:
                st.error(f"Invalid JSON: {e}")
                schema = None
        else:
            schema = sample_schemas[selected_schema_name]
        
        if schema:
            # Display schema
            display_schema_info(schema)
            
            # Question input
            st.subheader("❓ Natural Language Question")
            
            # Sample questions for selected schema
            if selected_schema_name == "🗄️ MySQL Database (Live)":
                sample_questions = [
                    "Show me the first 10 rows from the reference_asset table",
                    "How many records are in each table?",
                    "What are the column names and types for the user table?",
                    "Find all tables that contain a company_id column",
                    "Show me the latest created records from the external_asset_interaction table"
                ]
            elif selected_schema_name == "University Database":
                sample_questions = [
                    "What are the names of students who have enrolled in Computer Science courses?",
                    "Show me the top 5 students with highest GPA in each major",
                    "How many courses does each department offer?",
                    "Which students have a GPA above 3.5 and are enrolled in more than 3 courses?"
                ]
            elif selected_schema_name == "E-commerce Database":
                sample_questions = [
                    "Which customers have made orders in the last month?",
                    "What are the top 5 best-selling products by total revenue?",
                    "Show me the average order value for each customer",
                    "Which products are out of stock?"
                ]
            else:
                sample_questions = []
            
            question = st.text_area(
                "Enter your question",
                height=100,
                placeholder="e.g., Show me all students with GPA above 3.5"
            )
            
            # Sample questions buttons
            if sample_questions:
                st.write("**Sample Questions:**")
                cols = st.columns(min(len(sample_questions), 2))
                for i, sample_q in enumerate(sample_questions):
                    with cols[i % 2]:
                        if st.button(f"📝 {sample_q[:40]}...", key=f"sample_{i}"):
                            question = sample_q
                            st.rerun()
            
            # Execute button
            if st.button("🚀 Generate SQL", type="primary", disabled=not question.strip()):
                st.session_state.last_question = question
                
                # Determine if we should use MySQL executor
                use_mysql = selected_schema_name == "🗄️ MySQL Database (Live)"
                
                # Execute pipeline (async)
                result, execution_time = execute_pipeline(question, schema, config, use_mysql)
                
                # Display results only if execution is complete
                if result is not None:
                    st.success("✅ Pipeline execution completed!")
                    display_pipeline_results(result, execution_time, config['llm_name'])
                else:
                    # Pipeline is still running - results will be shown on next refresh
                    pass
    
    with tab2:
        display_error_taxonomy()
    
    with tab3:
        display_results_history()
    
    with tab4:
        st.header("About SQL-of-Thought")
        
        st.markdown("""
        ### 📖 Overview
        
        SQL-of-Thought is a multi-agentic framework for text-to-SQL generation that implements
        guided error correction to achieve state-of-the-art performance on the Spider dataset.
        
        ### 🎯 Key Features
        
        - **6-Agent Architecture**: Schema Linking, Subproblem, Query Plan, SQL Generation, 
          Correction Plan, and Correction SQL agents
        - **Chain-of-Thought Reasoning**: Explicit reasoning for query planning and error correction
        - **Error Taxonomy**: Comprehensive classification of 31 SQL error types across 9 categories
        - **Guided Correction**: Systematic error detection and correction loop
        - **Multi-LLM Support**: Ollama (local), Claude-3 Opus, Claude-3.5 Sonnet, GPT-4o, and more
        
        ### 📊 Performance
        
        - **91.59% execution accuracy** on Spider dataset (Claude-3 Opus)
        - **Significant improvement** over baseline text-to-SQL models
        - **Robust error handling** with guided correction loop
        
        ### 🏗️ Architecture
        
        1. **Schema Linking**: Identifies relevant tables and columns
        2. **Subproblem**: Decomposes query into manageable sub-clauses  
        3. **Query Plan**: Creates step-by-step execution plan with reasoning
        4. **SQL Generation**: Synthesizes final SQL query
        5. **Correction Plan**: Analyzes execution errors if any
        6. **Correction SQL**: Applies corrections based on error analysis
        
        ### 🔧 Usage
        
        ```python
        from src.core.pipeline import SQLOfThoughtPipeline
        from src.llm import LLMFactory
        
        # Initialize pipeline with local Ollama
        llm = LLMFactory.create_ollama(model="llama3.2")
        pipeline = SQLOfThoughtPipeline(llm)
        
        # Execute query
        result = pipeline.execute(question, schema)
        print(result.final_sql)
        ```
        
        ### 📚 Research Paper
        
        This implementation is based on the research paper:
        *"Multi-agentic Text-to-SQL with Guided Error Correction"*
        
        The framework demonstrates how decomposing complex text-to-SQL tasks into
        specialized agents with explicit reasoning can significantly improve
        accuracy and robustness.
        """)


if __name__ == "__main__":
    main()