# 🤖 AI Document Processing Agent

> **A production-grade, asynchronous document processing pipeline built with FastAPI, LangGraph, and CrewAI.**

This system ingests unstructured documents (Invoices, Contracts, Emails), intelligently classifies them using LLM agents, extracts structured JSON data, and handles edge cases with smart routing logic.

---

## 🚀 Features

* **⚡ Asynchronous Architecture**: Powered by **Celery** & **Redis** to decouple API ingestion from heavy AI processing, ensuring high concurrency and non-blocking responses.
* **🧠 Intelligent Classification**: Uses **CrewAI** agents (Llama 3.1) to analyze document content and determine types (Invoice, Contract, Technical Spec) with confidence scores.
* **🔀 Smart Routing (LangGraph)**:
    * **High Confidence (>70%)**: Automatically routed to specialized extraction agents.
    * **Low Confidence (<70%)**: Flagged and routed to a "Manual Review" queue, optimizing accuracy and cost.
* **📊 Structured Extraction**: Enforces strict JSON schemas for all outputs, converting messy text into reliable data.
* **🛡️ Robust Error Handling**: Gracefully handles empty files, vague content, and JSON parsing errors without crashing.

---

## 🛠️ Tech Stack

| Component | Technology | Purpose |
| :--- | :--- | :--- |
| **API Layer** | **FastAPI** | High-performance REST API for file uploads. |
| **Orchestration** | **LangGraph** | Stateful workflow management and conditional routing. |
| **Agents** | **CrewAI** | Agentic logic and LLM interaction (via Groq). |
| **Queue** | **Celery** | Distributed task queue for async background jobs. |
| **Broker** | **Redis** | Message broker and result backend. |

---

## 📋 Prerequisites

Before running the system, ensure you have the following installed:

* **Python 3.9+**
* **Redis Server** (Running locally on default port `6379`)

---

## ⚙️ Installation

1.  **Clone the Repository**
    ```bash
    git clone [https://github.com/Devarsh009/ai-document-processing-agent.git](https://github.com/Devarsh009/ai-document-processing-agent.git)
    cd ai-document-processing-agent
    ```

2.  **Create Virtual Environment**
    ```bash
    # Windows
    python -m venv venv
    .\venv\Scripts\activate

    # Mac/Linux
    python3 -m venv venv
    source venv/bin/activate
    ```

3.  **Install Dependencies**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configure Environment**
    Create a `.env` file in the root directory:
    ```env
    GROQ_API_KEY=gsk_your_actual_api_key_here
    ```

---

## 🏃‍♂️ How to Run

To run the full pipeline, you need **three separate terminal windows**:

### 1️⃣ Start Redis
Ensure your local Redis server is active.
```bash
redis-server

# Windows (Use --pool=solo)
python -m celery -A app.workers.celery_app:celery_app worker --loglevel=info --pool=solo

# Mac/Linux
python -m celery -A app.workers.celery_app:celery_app worker --loglevel=info

uvicorn app.main:app --reload