import hashlib
import os
import uuid
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Literal, Optional

import redis
from fastapi import FastAPI, File, HTTPException, UploadFile, status
from pydantic import BaseModel, Field

from app.config import settings
from app.parsers.document_parser import (
    DocumentExceedsSizeLimitError,
    UnsupportedFileTypeError,
    validate_file_bytes,
)
from app.storage.repository import (
    check_storage_health,
    create_job,
    get_job,
    init_db,
    record_review_decision,
    update_job_status,
)
from app.utils.logger import get_logger
from app.workers.celery_app import celery_app
from app.workers.tasks import process_document_task

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle management."""
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    init_db()
    if not settings.GROQ_API_KEY:
        logger.warning(
            "GROQ_API_KEY is not set. Prototype will queue documents, "
            "but LLM agent execution in workers will require GROQ_API_KEY."
        )
    yield


app = FastAPI(
    title="AI Document Intelligence Agent API",
    description="Asynchronous document ingestion, multi-format parsing, extraction, and validation pipeline.",
    version="0.2.0",
    lifespan=lifespan,
)


# --- Schemas ---


class DocumentSubmissionResponse(BaseModel):
    id: str = Field(..., description="Unique document processing ID")
    status: str = Field(..., description="Current lifecycle state (e.g. 'queued')")
    filename: str = Field(..., description="Sanitized original filename")
    status_url: str = Field(..., description="URL to poll for processing status")
    created_at: str = Field(..., description="UTC timestamp of submission")


class DocumentStatusDetail(BaseModel):
    id: str
    status: str
    processing_stage: str
    filename: str
    content_type: str
    file_size_bytes: int
    sha256_checksum: str
    classification: Optional[str] = None
    confidence_score: Optional[float] = None
    validation_errors: Optional[List[str]] = None
    review_decision: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    duration_ms: Optional[float] = None
    created_at: str
    updated_at: str
    completed_at: Optional[str] = None


class DocumentResultResponse(BaseModel):
    id: str
    status: str
    classification: Optional[str] = None
    confidence_score: Optional[float] = None
    extracted_data: Optional[Dict[str, Any]] = None
    validation_errors: Optional[List[str]] = None
    review_decision: Optional[Dict[str, Any]] = None
    duration_ms: Optional[float] = None
    completed_at: Optional[str] = None


class ReviewRequest(BaseModel):
    action: Literal["approve", "reject", "override"] = Field(
        ..., description="Review action: approve, reject, or override"
    )
    notes: Optional[str] = Field(None, description="Auditor review rationale")
    overrides: Optional[Dict[str, Any]] = Field(
        None, description="Corrected key-value pairs when action is 'override'"
    )


class HealthResponse(BaseModel):
    status: str
    app: str
    version: str


class ReadinessResponse(BaseModel):
    status: str
    database: bool
    broker: bool
    storage_writable: bool


# --- Helper ---


def _validate_uuid(doc_id: str) -> None:
    try:
        uuid.UUID(doc_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid document ID format. Must be a valid UUID.",
        )


# --- Liveness and Readiness ---


@app.get("/health", response_model=HealthResponse, tags=["System"])
@app.get("/v1/health", response_model=HealthResponse, tags=["System"])
async def health_check():
    """Liveness probe indicating that the web service process is running."""
    return HealthResponse(
        status="ok",
        app="ai-document-processing-agent",
        version="0.2.0",
    )


@app.get("/ready", response_model=ReadinessResponse, tags=["System"])
@app.get("/v1/ready", response_model=ReadinessResponse, tags=["System"])
async def readiness_check():
    """Readiness probe validating database, Redis broker, and filesystem storage."""
    db_ok = check_storage_health()

    broker_ok = False
    try:
        r = redis.Redis.from_url(settings.REDIS_URL, socket_timeout=2.0)
        broker_ok = bool(r.ping())
    except Exception as e:
        logger.warning(f"Redis readiness check failed: {e}")

    storage_ok = False
    try:
        test_file = os.path.join(settings.UPLOAD_DIR, ".ready_check")
        with open(test_file, "w") as f:
            f.write("ok")
        if os.path.exists(test_file):
            os.remove(test_file)
        storage_ok = True
    except Exception as e:
        logger.warning(f"Storage directory write check failed: {e}")

    all_ready = db_ok and broker_ok and storage_ok
    resp = ReadinessResponse(
        status="ready" if all_ready else "not_ready",
        database=db_ok,
        broker=broker_ok,
        storage_writable=storage_ok,
    )
    if not all_ready:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=resp.model_dump(),
        )
    return resp


# --- Document Lifecycle Endpoints ---


@app.post(
    "/v1/documents",
    response_model=DocumentSubmissionResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["Documents"],
)
async def submit_document(file: UploadFile = File(...)):
    """
    Submits a document (TXT, PDF, DOCX) for asynchronous processing.
    Validates file signature, size, persists job to DB, and enqueues task in Celery.
    Returns HTTP 202 with status URL.
    """
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file must have a non-empty filename.",
        )

    try:
        content_bytes = await file.read()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to read upload payload: {e}",
        )

    try:
        ext, content_type = validate_file_bytes(content_bytes, file.filename)
    except DocumentExceedsSizeLimitError as e:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=str(e))
    except UnsupportedFileTypeError as e:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=str(e))

    doc_id = str(uuid.uuid4())
    safe_filename = os.path.basename(file.filename)
    checksum = hashlib.sha256(content_bytes).hexdigest()

    # Server-controlled safe storage filename
    server_filename = f"{doc_id}{ext}"
    file_path = os.path.join(settings.UPLOAD_DIR, server_filename)

    try:
        with open(file_path, "wb") as f:
            f.write(content_bytes)
    except Exception as e:
        logger.error(f"Failed to persist file: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to persist file to server storage.",
        )

    # Persist job record
    create_job(
        doc_id=doc_id,
        filename=safe_filename,
        content_type=content_type,
        file_size_bytes=len(content_bytes),
        file_path=file_path,
        sha256_checksum=checksum,
        status="received",
        processing_stage="ingest",
    )

    # Enqueue task in Celery
    try:
        process_document_task.apply_async(args=[doc_id, file_path], task_id=doc_id)
        update_job_status(doc_id, "queued", processing_stage="ingest")
    except Exception as e:
        logger.error(f"Failed to enqueue task in Celery: {e}")
        update_job_status(
            doc_id, "failed", processing_stage="ingest", error_message="Failed to enqueue to task broker."
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Task broker (Redis) is currently unreachable. Document staged but not enqueued.",
        )

    logger.info(f"Accepted document {doc_id} ({safe_filename})")
    job = get_job(doc_id)
    return DocumentSubmissionResponse(
        id=doc_id,
        status="queued",
        filename=safe_filename,
        status_url=f"/v1/documents/{doc_id}",
        created_at=job["created_at"],
    )


@app.get(
    "/v1/documents/{doc_id}",
    response_model=DocumentStatusDetail,
    tags=["Documents"],
)
async def get_document(doc_id: str):
    """Retrieves document lifecycle state, metadata, and stage."""
    _validate_uuid(doc_id)
    job = get_job(doc_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document '{doc_id}' not found.",
        )

    return DocumentStatusDetail(**job)


@app.get(
    "/v1/documents/{doc_id}/result",
    response_model=DocumentResultResponse,
    tags=["Documents"],
)
async def get_document_result(doc_id: str):
    """
    Retrieves extraction result for a processed document.
    Returns 409 Conflict if still processing.
    """
    _validate_uuid(doc_id)
    job = get_job(doc_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document '{doc_id}' not found.",
        )

    current_status = job["status"]
    if current_status in ("received", "queued", "processing"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Document is not ready. Current state: '{current_status}'.",
        )

    return DocumentResultResponse(
        id=job["id"],
        status=job["status"],
        classification=job.get("classification"),
        confidence_score=job.get("confidence_score"),
        extracted_data=job.get("extracted_data"),
        validation_errors=job.get("validation_errors"),
        review_decision=job.get("review_decision"),
        duration_ms=job.get("duration_ms"),
        completed_at=job.get("completed_at"),
    )


@app.post(
    "/v1/documents/{doc_id}/review",
    response_model=DocumentStatusDetail,
    tags=["Documents"],
)
async def review_document(doc_id: str, payload: ReviewRequest):
    """
    Submits a human review decision for a document in 'needs_review' state.
    Legal actions: 'approve', 'reject', 'override'.
    """
    _validate_uuid(doc_id)
    job = get_job(doc_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document '{doc_id}' not found.",
        )

    if job["status"] != "needs_review":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Document is in '{job['status']}' state. Only documents in 'needs_review' can be reviewed.",
        )

    try:
        updated = record_review_decision(
            doc_id=doc_id,
            action=payload.action,
            notes=payload.notes,
            overrides=payload.overrides,
        )
        logger.info(f"Recorded human review decision '{payload.action}' for document {doc_id}")
        return DocumentStatusDetail(**updated)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# --- Backwards Compatibility Endpoints ---


@app.post("/process", tags=["Legacy"])
async def legacy_process_document(file: UploadFile = File(...)):
    """Legacy endpoint mapping to POST /v1/documents."""
    sub = await submit_document(file)
    return {
        "status": sub.status,
        "doc_id": sub.id,
        "filename": sub.filename,
    }


@app.get("/status/{doc_id}", tags=["Legacy"])
async def legacy_get_status(doc_id: str):
    """Legacy endpoint mapping to GET /v1/documents/{doc_id}."""
    _validate_uuid(doc_id)
    job = get_job(doc_id)
    if not job:
        raise HTTPException(status_code=404, detail="Document not found.")

    res = None
    if job["status"] in ("succeeded", "needs_review"):
        res = {
            "doc_id": job["id"],
            "classification": job.get("classification"),
            "confidence_score": job.get("confidence_score"),
            "extracted_data": job.get("extracted_data") or {},
            "validation_errors": job.get("validation_errors") or [],
            "next_step": "manual_review" if job["status"] == "needs_review" else None,
        }

    status_map = {
        "received": "queued",
        "queued": "queued",
        "processing": "processing",
        "needs_review": "completed",
        "succeeded": "completed",
        "failed": "failed",
        "rejected": "failed",
    }

    return {
        "doc_id": job["id"],
        "status": status_map.get(job["status"], job["status"]),
        "filename": job["filename"],
        "result": res,
        "error": job.get("error_message"),
    }