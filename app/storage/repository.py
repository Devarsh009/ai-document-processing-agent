import datetime
import json
import sqlite3
from typing import Any, Dict, List, Optional
from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Valid job states
VALID_STATES = {
    "received",
    "queued",
    "processing",
    "needs_review",
    "succeeded",
    "failed",
    "rejected",
}

# Legal state transitions
ALLOWED_TRANSITIONS = {
    "received": {"queued", "failed"},
    "queued": {"processing", "failed"},
    "processing": {"succeeded", "needs_review", "failed"},
    "needs_review": {"succeeded", "rejected"},
    "succeeded": set(),
    "failed": set(),
    "rejected": set(),
}


def _get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(settings.DATABASE_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn


def init_db() -> None:
    """Initializes the database schema if not present."""
    with _get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS document_jobs (
                id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                content_type TEXT NOT NULL,
                file_size_bytes INTEGER NOT NULL,
                file_path TEXT NOT NULL,
                sha256_checksum TEXT NOT NULL,
                status TEXT NOT NULL,
                processing_stage TEXT NOT NULL,
                classification TEXT,
                confidence_score REAL,
                extracted_data TEXT,
                validation_errors TEXT,
                review_decision TEXT,
                error_message TEXT,
                duration_ms REAL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                completed_at TEXT
            );
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_jobs_status ON document_jobs(status);"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_jobs_checksum ON document_jobs(sha256_checksum);"
        )
        conn.commit()


def _row_to_dict(row: sqlite3.Row) -> dict:
    data = dict(row)
    if data.get("extracted_data"):
        try:
            data["extracted_data"] = json.loads(data["extracted_data"])
        except (json.JSONDecodeError, TypeError):
            pass
    if data.get("validation_errors"):
        try:
            data["validation_errors"] = json.loads(data["validation_errors"])
        except (json.JSONDecodeError, TypeError):
            pass
    if data.get("review_decision"):
        try:
            data["review_decision"] = json.loads(data["review_decision"])
        except (json.JSONDecodeError, TypeError):
            pass
    return data


def create_job(
    doc_id: str,
    filename: str,
    content_type: str,
    file_size_bytes: int,
    file_path: str,
    sha256_checksum: str,
    status: str = "received",
    processing_stage: str = "ingest",
) -> dict:
    """Creates a new job record with initial status."""
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    init_db()
    with _get_connection() as conn:
        conn.execute(
            """
            INSERT INTO document_jobs (
                id, filename, content_type, file_size_bytes, file_path,
                sha256_checksum, status, processing_stage, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                doc_id,
                filename,
                content_type,
                file_size_bytes,
                file_path,
                sha256_checksum,
                status,
                processing_stage,
                now,
                now,
            ),
        )
        conn.commit()

    return get_job(doc_id)  # type: ignore


def get_job(doc_id: str) -> Optional[dict]:
    """Retrieves a job by its unique document ID."""
    init_db()
    with _get_connection() as conn:
        cursor = conn.execute(
            "SELECT * FROM document_jobs WHERE id = ?;", (doc_id,)
        )
        row = cursor.fetchone()
        return _row_to_dict(row) if row else None


def update_job_status(
    doc_id: str,
    new_status: str,
    processing_stage: Optional[str] = None,
    classification: Optional[str] = None,
    confidence_score: Optional[float] = None,
    extracted_data: Optional[Dict[str, Any]] = None,
    validation_errors: Optional[List[str]] = None,
    error_message: Optional[str] = None,
    duration_ms: Optional[float] = None,
) -> Optional[dict]:
    """Updates job state enforcing valid transitions."""
    init_db()
    job = get_job(doc_id)
    if not job:
        logger.warning(f"Attempted to update non-existent job: {doc_id}")
        return None

    current_status = job["status"]
    if new_status != current_status:
        allowed = ALLOWED_TRANSITIONS.get(current_status, set())
        if new_status not in allowed:
            raise ValueError(
                f"Illegal state transition from '{current_status}' to '{new_status}'."
            )

    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    completed_at = now if new_status in ("succeeded", "failed", "rejected") else job.get("completed_at")

    ext_json = json.dumps(extracted_data) if extracted_data is not None else job.get("extracted_data")
    if isinstance(ext_json, dict):
        ext_json = json.dumps(ext_json)

    errs_json = json.dumps(validation_errors) if validation_errors is not None else job.get("validation_errors")
    if isinstance(errs_json, list):
        errs_json = json.dumps(errs_json)

    with _get_connection() as conn:
        conn.execute(
            """
            UPDATE document_jobs SET
                status = ?,
                processing_stage = COALESCE(?, processing_stage),
                classification = COALESCE(?, classification),
                confidence_score = COALESCE(?, confidence_score),
                extracted_data = ?,
                validation_errors = ?,
                error_message = COALESCE(?, error_message),
                duration_ms = COALESCE(?, duration_ms),
                updated_at = ?,
                completed_at = ?
            WHERE id = ?;
            """,
            (
                new_status,
                processing_stage,
                classification,
                confidence_score,
                ext_json,
                errs_json,
                error_message,
                duration_ms,
                now,
                completed_at,
                doc_id,
            ),
        )
        conn.commit()

    return get_job(doc_id)


def record_review_decision(
    doc_id: str,
    action: str,
    notes: Optional[str] = None,
    overrides: Optional[Dict[str, Any]] = None,
) -> dict:
    """
    Records a human review decision and transitions state.
    Allowed actions: 'approve', 'reject', 'override'.
    """
    init_db()
    job = get_job(doc_id)
    if not job:
        raise KeyError(f"Job '{doc_id}' not found.")

    if job["status"] != "needs_review":
        raise ValueError(
            f"Cannot review document in '{job['status']}' state. Only 'needs_review' documents can be reviewed."
        )

    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    review_record = {
        "action": action,
        "notes": notes,
        "overrides": overrides,
        "reviewed_at": now,
    }

    if action == "approve":
        new_status = "succeeded"
        final_extracted = job.get("extracted_data")
    elif action == "override":
        new_status = "succeeded"
        current_data = job.get("extracted_data") or {}
        if isinstance(current_data, str):
            try:
                current_data = json.loads(current_data)
            except Exception:
                current_data = {}
        if overrides:
            current_data.update(overrides)
        final_extracted = current_data
    elif action == "reject":
        new_status = "rejected"
        final_extracted = job.get("extracted_data")
    else:
        raise ValueError(f"Unknown review action: '{action}'")

    with _get_connection() as conn:
        conn.execute(
            """
            UPDATE document_jobs SET
                status = ?,
                processing_stage = 'completed',
                extracted_data = ?,
                review_decision = ?,
                updated_at = ?,
                completed_at = ?
            WHERE id = ?;
            """,
            (
                new_status,
                json.dumps(final_extracted) if final_extracted else None,
                json.dumps(review_record),
                now,
                now,
                doc_id,
            ),
        )
        conn.commit()

    return get_job(doc_id)  # type: ignore


def check_storage_health() -> bool:
    """Verifies that the database is reachable and writable."""
    try:
        init_db()
        with _get_connection() as conn:
            conn.execute("SELECT 1 FROM document_jobs LIMIT 1;")
        return True
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return False
