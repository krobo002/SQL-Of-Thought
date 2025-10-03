# SQL-of-Thought: MVP Implementation

![Python](https://img.shields.io/badge/Python-3.9%2B-blue.svg)
![Framework](https://img.shields.io/badge/Framework-FastAPI%20%7C%20Streamlit-green.svg)
![License](https://img.shields.io/badge/License-MIT-lightgrey.svg)

[cite_start]This repository contains a Minimum Viable Product (MVP) implementation of the research paper: **"SQL-of-Thought: Multi-agentic Text-to-SQL with Guided Error Correction"**[cite: 2, 3]. [cite_start]The project translates a natural language question into an executable SQL query by orchestrating a series of LLM-powered "agents," each responsible for a specific step in the reasoning process[cite: 17, 31, 32].

[cite_start]The core innovation demonstrated is the **Guided Correction Loop**, which uses a predefined error taxonomy to intelligently correct failed SQL queries[cite: 17, 33, 63]. [cite_start]This approach is a significant improvement over simple execution-based feedback[cite: 26, 60, 161].

## ✨ Core Features

* [cite_start]**Multi-Agent Pipeline**: Decomposes the Text-to-SQL task into modular steps: Schema Linking, Subproblem Identification, Query Planning, and SQL Generation[cite: 17, 32].
* [cite_start]**Chain-of-Thought (CoT) Reasoning**: The Query Plan Agent explicitly generates a step-by-step reasoning plan before writing the final SQL, improving alignment with user intent[cite: 53, 115].
* [cite_start]**Taxonomy-Guided Error Correction**: If a query fails, a correction loop is triggered[cite: 55]. [cite_start]A `CorrectionPlanAgent` uses a comprehensive error taxonomy (see Figure 2 in the paper) to diagnose the failure and propose a fix[cite: 33, 43, 55, 122, 124].
* **Interactive Web UI**: A simple Streamlit application allows users to input a question, select a database, and visualize the output from each agent in the pipeline.

---

## 🏛️ Architecture

The application follows a simple three-tier architecture:

1.  **Frontend**: A web interface built with **Streamlit** for rapid, interactive prototyping.
2.  **Backend**: A REST API built with **FastAPI** that exposes the core logic for generating SQL.
3.  **ML Core**: A set of Python modules that orchestrate the multi-agent pipeline by making sequential calls to an LLM API (e.g., OpenAI GPT-4o). [cite_start]The logic directly follows the architecture shown in Figure 1 of the paper[cite: 50].

![A placeholder image showing the UI of the SQL-of-Thought Streamlit application, with input fields for a natural language question and database ID, and expandable sections showing the outputs of each agent in the pipeline.](https://i.imgur.com/u5u2G2L.png)

---

## 🚀 Getting Started

Follow these instructions to set up and run the project locally.

### Prerequisites

* Python 3.9 or higher
* An OpenAI API Key

### 1. Clone the Repository

```bash
git clone [https://github.com/krobo002/SQL-Of-Thought.git](https://github.com/krobo002/SQL-Of-Thought.git)
cd sql-of-thought-mvp