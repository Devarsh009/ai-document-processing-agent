Here is a complete, visually engaging, and professional `README.md` file. It includes emojis, clear formatting, and precise technical details. You can copy and paste this directly into your `README.md` file.

```markdown
# 🤖 AI Document Processing Agent

> **A production-grade, asynchronous document processing pipeline built with FastAPI, LangGraph, and CrewAI.**

This system ingests unstructured documents (Invoices, Contracts, Emails), intelligently classifies them using LLM agents, extracts structured JSON data, and handles edge cases with smart routing logic.

---

## 🚀 Features

* [cite_start]**⚡ Asynchronous Architecture**: Powered by **Celery** & **Redis** to decouple API ingestion from heavy AI processing, ensuring high concurrency and non-blocking responses[cite: 55].
* [cite_start]**🧠 Intelligent Classification**: Uses **CrewAI** agents (Llama 3.1) to analyze document content and determine types (Invoice, Contract, Technical Spec) with confidence scores [cite: 20-22].
* **🔀 Smart Routing (LangGraph)**:
    * [cite_start]**High Confidence (>70%)**: Automatically routed to specialized extraction agents [cite: 33-34].
    * [cite_start]**Low Confidence (<70%)**: Flagged and routed to a "Manual Review" queue, optimizing accuracy and cost[cite: 32].
* [cite_start]**📊 Structured Extraction**: Enforces strict JSON schemas for all outputs, converting messy text into reliable data[cite: 25].
* [cite_start]**🛡️ Robust Error Handling**: Gracefully handles empty files, vague content, and JSON parsing errors without crashing[cite: 73].

---

## 🛠️ Tech Stack

| Component | Technology | Purpose |
| :--- | :--- | :--- |
| **API Layer** | **FastAPI** | [cite_start]High-performance REST API for file uploads[cite: 9]. |
| **Orchestration** | **LangGraph** | [cite_start]Stateful workflow management and conditional routing[cite: 10]. |
| **Agents** | **CrewAI** | [cite_start]Agentic logic and LLM interaction (via Groq)[cite: 11]. |
| **Queue** | **Celery** | Distributed task queue for async background jobs. |
| **Broker** | **Redis** | Message broker and result backend. |

---

## 📋 Prerequisites

Before running the system, ensure you have the following installed:

* [cite_start]**Python 3.9+** [cite: 107]
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

```

### 2️⃣ Start Celery Worker

This background worker listens for and executes AI tasks.

```bash
# Windows (Use --pool=solo)
python -m celery -A app.workers.celery_app:celery_app worker --loglevel=info --pool=solo

# Mac/Linux
python -m celery -A app.workers.celery_app:celery_app worker --loglevel=info

```

### 3️⃣ Start FastAPI Server

This launches the REST API at `http://127.0.0.1:8000`.

```bash
uvicorn app.main:app --reload

```

---

## 🧪 Testing the System

### Option A: Automated Concurrent Test ⚡

Use the included script to simulate multiple users uploading different documents simultaneously.

1. Ensure sample files exist in the `test_samples/` folder.
2. Run the script:
```bash
python test_script.py

```


3. **Watch the Magic**: Check your **Celery Terminal** to see agents processing files in parallel!

### Option B: Manual API Testing 🖐️

1. Open the interactive Swagger UI: [http://127.0.0.1:8000/docs](https://www.google.com/search?q=http://127.0.0.1:8000/docs)
2. Use the `POST /process` endpoint.
3. Upload a `.txt` file.
4. The API returns a **Task ID**. Check the Celery logs for the JSON result.

---

## 📂 Project Structure

```text
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

```

---

## 🛡️ Edge Case Handling

The system is designed to handle real-world messiness:

* **Vague/Empty Files**: Caught by the Classifier logic and routed to `Manual Review`.
* **Hallucinations**: Strict prompt engineering enforces JSON-only responses.
* **JSON Errors**: A dedicated cleaning utility strips Markdown formatting before parsing.

---

**Author**: Devarsh

```

```