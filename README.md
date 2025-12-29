# 🤖 AI Document Processing Agent

> **A production-grade, asynchronous document processing pipeline built with FastAPI, LangGraph, and CrewAI.**

This system ingests unstructured documents (Invoices, Contracts, Emails), intelligently classifies them using LLM agents, extracts structured JSON data, and handles edge cases with smart routing logic.

---

## 🚀 Features

* **⚡ Asynchronous Architecture**: Powered by **Celery** & **Redis** to decouple API ingestion from heavy AI processing, ensuring high concurrency and non-blocking responses.
* **🧠 Intelligent "Skeptical Auditor"**: Uses **Chain-of-Thought (CoT)** prompting to distinguish between actual business documents and informal emails *discussing* them.
* **🔀 Smart Routing (LangGraph)**:
    * **High Confidence (≥70%)**: Automatically routed to specialized extraction agents.
    * **Low Confidence (<70%)**: Flagged and routed to a "Manual Review" queue, optimizing accuracy and ensuring safety.
* **📊 Structured Extraction**: Enforces strict JSON schemas for all outputs, converting messy text into reliable data.
* **🛡️ Robust Error Handling**: Gracefully handles empty files, vague content, and JSON parsing errors without crashing.

---

## 🔄 Architecture & Workflow

1.  **Ingestion 📥**: User uploads a file via **FastAPI** (Non-blocking). The task is immediately pushed to **Redis**.
2.  **Async Processing ⚙️**: A background **Celery Worker** picks up the task from the queue.
3.  **Smart Classification (The Brain) 🧠**:
    * The **Classification Agent** analyzes the text using Llama 3.1.
    * *Logic Check:* It asks, "Is this the document itself, or just an email talking about it?"
    * Assigns a `Classification` and a `Confidence Score`.
4.  **Conditional Routing (LangGraph) 🔀**:
    * ✅ **Score ≥ 70%**: Routes to the specific **Extractor Agent** (e.g., `Invoice Extractor`).
    * ⚠️ **Score < 70%**: Routes to the **Manual Review** node.
5.  **Extraction 📝**: Returns structured JSON (Pydantic-validated) containing fields like `Total`, `Vendor`, `Dates`, etc.

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
2️⃣ Start Celery Worker
This background worker listens for and executes AI tasks.

Bash

# Windows (Use --pool=solo)
python -m celery -A app.workers.celery_app:celery_app worker --loglevel=info --pool=solo

# Mac/Linux
python -m celery -A app.workers.celery_app:celery_app worker --loglevel=info
3️⃣ Start FastAPI Server
This launches the REST API at http://127.0.0.1:8000.

Bash

uvicorn app.main:app --reload
🧪 Testing the System
Option A: Automated Concurrent Test ⚡
Use the included script to simulate multiple users uploading different documents simultaneously.

Ensure sample files exist in the test_samples/ folder.

Run the script:

Bash

python test_script.py
Watch the Magic: Check your Celery Terminal to see agents processing files in parallel!

Option B: Manual API Testing 🖐️
Open the interactive Swagger UI: http://127.0.0.1:8000/docs

Use the POST /process endpoint.

Upload a .txt file.

The API returns a Task ID. Check the Celery logs for the JSON result.

📂 Project Structure
Plaintext

AI_PROJECT/
├── app/
│   ├── agents/           # 🤖 CrewAI Agent definitions (Classifier, Extractor)
│   ├── workers/          # ⚙️ Celery task configuration
│   ├── workflows/        # 🔀 LangGraph nodes & conditional logic
│   ├── utils/            # 📝 Logging & helpers
│   └── main.py           # 🌐 FastAPI entry point
├── test_samples/         # 📄 Sample documents (Invoice, Contract, Email)
├── uploads/              # 📂 Temp storage for processing
├── test_script.py        # 🧪 Concurrent testing tool
├── requirements.txt      # 📦 Pinned dependencies
└── README.md             # 📖 Documentation
🛡️ Edge Case Handling
The system is designed to handle real-world messiness:

Vague/Conversational Files: Caught by the "Skeptical Auditor" classifier logic (low confidence) and routed to Manual Review.

Hallucinations: Strict prompt engineering enforces JSON-only responses.

JSON Errors: A dedicated cleaning utility strips Markdown formatting before parsing.

Author: Devarsh