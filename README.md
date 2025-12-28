AI Document Processing Pipeline
This repository contains a production-grade document processing system designed to ingest, classify, and extract structured data from unstructured text documents. The architecture prioritizes resilience and concurrency by decoupling the API layer from the processing logic using an asynchronous task queue.

System Architecture
The solution integrates three core frameworks to handle the document lifecycle:

FastAPI (API Layer): Handles HTTP requests and file uploads. It acts as the entry point, immediately offloading processing tasks to the background queue to ensure non-blocking response times.

LangGraph (Orchestration): Manages the workflow logic. It treats the processing pipeline as a stateful graph, determining the flow of a document based on classification results and confidence scores.

CrewAI (Agentic Logic): Implements specialized AI agents (Classifier and Extractor) powered by Large Language Models to perform cognitive analysis on the document content.

Celery & Redis (Async Execution): Manages the task queue, allowing the system to process multiple documents concurrently without degrading API performance.

Key Features
Asynchronous Design: Long-running AI inference tasks are processed in the background, allowing the system to scale under load.

Intelligent Routing: The workflow includes conditional logic. Documents with high classification confidence are automatically routed for data extraction, while low-confidence documents are flagged and routed to a manual review queue.

Structured Data Extraction: The system enforces strict JSON schemas for outputs, ensuring that unstructured text (like invoices or contracts) is converted into reliable, machine-readable data.

Robust Error Handling: Specific edge cases, such as empty files, vague content, or LLM hallucinations, are caught and handled gracefully to prevent system crashes.

Prerequisites
Before running the application, ensure you have the following installed:

Python 3.9+

Redis Server: This is required for Celery to function as a message broker. It must be running locally on port 6379.

Installation Instructions
Clone the repository Navigate to the project directory on your local machine.

Set up the environment Create a virtual environment to isolate dependencies.

Bash

# Windows
python -m venv venv
.\venv\Scripts\activate

# Mac/Linux
python3 -m venv venv
source venv/bin/activate
Install dependencies Install the required Python packages specified in the requirements file.

Bash

pip install -r requirements.txt
Configure Environment Variables Create a file named .env in the root directory. Add your Groq API key (or other LLM provider key) here.

Plaintext

GROQ_API_KEY=your_api_key_here
How to Run the System
To run the full pipeline, you will need three separate terminal windows open to handle the different components of the architecture.

Terminal 1: Start Redis Ensure your local Redis instance is active.

Bash

redis-server
Terminal 2: Start the Celery Worker This launches the background worker that listens for processing tasks.

Bash

# Windows (The --pool=solo flag is often required for Windows compatibility)
python -m celery -A app.workers.celery_app:celery_app worker --loglevel=info --pool=solo

# Mac/Linux
python -m celery -A app.workers.celery_app:celery_app worker --loglevel=info
Terminal 3: Start the FastAPI Application This launches the web server to accept incoming requests.

Bash

uvicorn app.main:app --reload
Testing the Pipeline
Automated Concurrent Testing
A dedicated test script is included to simulate real-world usage. This script uploads multiple documents of different types (Invoice, Contract, Email) simultaneously to verify the system's concurrency and routing logic.

Ensure you have text files inside the test_samples/ directory.

Run the test script:

Bash

python test_script.py
Observe the Celery Terminal to watch the agents classify and extract data in parallel.

Manual API Testing
You can also interact with the API directly using the auto-generated Swagger documentation.

Open your web browser and navigate to http://127.0.0.1:8000/docs.

Locate the POST /process endpoint.

Upload a text file and execute the request.

The API will return a unique Task ID, and the processing result will appear in your Celery logs.

Project Structure
app/: Contains the core application source code.

agents/: Defines the CrewAI agents and their specific roles.

workers/: Configures the Celery application and task definitions.

workflows/: Contains the LangGraph state definitions, nodes, and routing logic.

utils/: Utility modules for logging and helper functions.

main.py: The FastAPI application entry point.

test_samples/: A directory containing sample text documents for testing purposes.

test_script.py: A Python script for running concurrent load tests against the API.

requirements.txt: A list of all project dependencies.