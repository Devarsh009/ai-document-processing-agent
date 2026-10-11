import os
import shutil
import uuid
from contextlib import asynccontextmanager
from typing import Any, Dict, Optional

from fastapi import FastAPI, File, HTTPException, UploadFile, status
from pydantic import BaseModel, Field

from app.config import settings
from app.utils.logger import get_logger
from app.workers.celery_app import celery_app
from app.workers.tasks import process_document_task

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle management."""
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    if not settings.GROQ_API_KEY:
        logger.warning(
            "GROQ_API_KEY is not set. Prototype will queue documents, "
            "but LLM agent execution in workers will require GROQ_API_KEY."
        )
    yield


app = FastAPI(
    title="AI Document Processing Agent API",
    description="Asynchronous document ingestion and intelligent processing pipeline prototype.",
    version="0.1.0",
    lifespan=lifespan,
)


class IngestionResponse(BaseModel):
    status: str = Field(..., description="Current job status (e.g. 'queued')")
    doc_id: str = Field(..., description="Unique document processing ID")
    filename: str = Field(..., description="Uploaded filename")


class DocumentStatusResponse(BaseModel):
    doc_id: str = Field(..., description="Unique document processing ID")
    status: str = Field(..., description="Processing status: queued, processing, completed, or failed")
    filename: Optional[str] = Field(None, description="Original filename if known")
    result: Optional[Dict[str, Any]] = Field(None, description="Workflow extraction result if completed")
    error: Optional[str] = Field(None, description="Error summary if failed")


class HealthResponse(BaseModel):
    status: str
    app: str
    version: str


@app.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check():
    """Service health check endpoint."""
    return HealthResponse(
        status="ok",
        app="ai-document-processing-agent",
        version="0.1.0",
    )


@app.post(
    "/process",
    response_model=IngestionResponse,
    status_code=status.HTTP_200_OK,
    tags=["Documents"],
)
async def process_document(file: UploadFile = File(...)):
    """
    Ingest a document file for asynchronous background classification and extraction.
    Returns a document ID to poll for status.
    """
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file must have a valid filename.",
        )

    doc_id = str(uuid.uuid4())
    safe_filename = os.path.basename(file.filename)
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    file_path = os.path.join(settings.UPLOAD_DIR, f"{doc_id}_{safe_filename}")

    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        logger.error(f"Failed to persist uploaded file: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save uploaded file.",
        )

    # Queue the task in Celery, associating task_id with doc_id
    try:
        process_document_task.apply_async(args=[doc_id, file_path], task_id=doc_id)
    except Exception as e:
        logger.error(f"Failed to enqueue task in Celery: {e}")
        # Clean up uploaded file if enqueuing fails
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except OSError:
                pass
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Task broker (Redis) is currently unreachable. Please verify Redis is running.",
        )

    logger.info(f"Queued document {doc_id} ({safe_filename})")
    return IngestionResponse(
        status="queued",
        doc_id=doc_id,
        filename=safe_filename,
    )


@app.get(
    "/status/{doc_id}",
    response_model=DocumentStatusResponse,
    tags=["Documents"],
)
async def get_document_status(doc_id: str):
    """
    Retrieve current processing status and results for a given document ID.
    """
    # 1. Validate doc_id format
    try:
        uuid.UUID(doc_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid doc_id format. Must be a valid UUID.",
        )

    # 2. Check for existence on disk
    filename: Optional[str] = None
    if os.path.exists(settings.UPLOAD_DIR):
        matching = [
            f for f in os.listdir(settings.UPLOAD_DIR) if f.startswith(f"{doc_id}_")
        ]
        if matching:
            filename = matching[0][len(doc_id) + 1 :]

    # 3. Query Celery task state
    try:
        async_result = celery_app.AsyncResult(doc_id)
        task_state = async_result.state
    except Exception as e:
        logger.error(f"Failed to connect to result backend: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Result backend (Redis) is unreachable.",
        )

    # If Celery is pending and no matching file was uploaded, document does not exist
    if task_state == "PENDING" and filename is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID '{doc_id}' not found.",
        )

    if task_state == "SUCCESS":
        return DocumentStatusResponse(
            doc_id=doc_id,
            status="completed",
            filename=filename,
            result=async_result.result,
        )
    elif task_state == "STARTED":
        return DocumentStatusResponse(
            doc_id=doc_id,
            status="processing",
            filename=filename,
        )
    elif task_state == "FAILURE":
        return DocumentStatusResponse(
            doc_id=doc_id,
            status="failed",
            filename=filename,
            error="Document processing failed during worker execution. See worker logs for details.",
        )
    elif task_state == "REVOKED":
        return DocumentStatusResponse(
            doc_id=doc_id,
            status="cancelled",
            filename=filename,
        )
    else:  # PENDING or unknown
        return DocumentStatusResponse(
            doc_id=doc_id,
            status="queued",
            filename=filename,
        )