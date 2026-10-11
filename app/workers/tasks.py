import time
from app.workflows.graph import run_workflow
from app.workers.celery_app import celery_app
from app.storage.repository import get_job, update_job_status
from app.utils.logger import get_logger

logger = get_logger(__name__)


@celery_app.task(name="process_document_task", bind=True, max_retries=3)
def process_document_task(self, doc_id: str, file_path: str = None):
    """
    Celery background worker task to run the LangGraph processing workflow.
    Coordinates state persistence via SQLite repository.
    """
    start_time = time.time()
    logger.info(f"[CELERY] Starting task {self.request.id} for document {doc_id}")

    job = get_job(doc_id)
    if not job:
        logger.error(f"[CELERY] Document job '{doc_id}' not found in database.")
        raise KeyError(f"Document job '{doc_id}' does not exist.")

    actual_file_path = file_path or job["file_path"]

    try:
        update_job_status(doc_id, "processing", processing_stage="ingest")
    except Exception as e:
        logger.warning(f"Failed to record processing state: {e}")

    try:
        result = run_workflow(doc_id, actual_file_path)
        duration_ms = (time.time() - start_time) * 1000.0

        next_step = result.get("next_step")
        validation_errors = result.get("validation_errors", [])
        classification = result.get("classification")
        confidence_score = result.get("confidence_score", 0.0)
        extracted_data = result.get("extracted_data", {})

        if next_step == "manual_review" or (validation_errors and len(validation_errors) > 0):
            logger.info(f"[CELERY] Document {doc_id} routed to manual review.")
            update_job_status(
                doc_id=doc_id,
                new_status="needs_review",
                processing_stage="review",
                classification=classification,
                confidence_score=confidence_score,
                extracted_data=extracted_data,
                validation_errors=validation_errors,
                duration_ms=duration_ms,
            )
        else:
            logger.info(f"[CELERY] Document {doc_id} processed successfully.")
            update_job_status(
                doc_id=doc_id,
                new_status="succeeded",
                processing_stage="completed",
                classification=classification,
                confidence_score=confidence_score,
                extracted_data=extracted_data,
                validation_errors=[],
                duration_ms=duration_ms,
            )

        return result

    except Exception as exc:
        duration_ms = (time.time() - start_time) * 1000.0
        logger.exception(f"[CELERY] Error processing document {doc_id}: {exc}")

        # Distinguish non-retryable errors
        err_str = str(exc)
        is_deterministic = "Corrupted" in err_str or "unsupported" in err_str.lower()

        if is_deterministic or self.request.retries >= self.max_retries:
            try:
                update_job_status(
                    doc_id=doc_id,
                    new_status="failed",
                    processing_stage="failed",
                    error_message=f"Processing failed: {err_str}",
                    duration_ms=duration_ms,
                )
            except Exception:
                pass
            raise exc

        # Transient error retry with exponential backoff
        countdown = 2 ** self.request.retries
        logger.warning(f"Retrying document {doc_id} in {countdown}s (retry {self.request.retries + 1}/{self.max_retries})")
        raise self.retry(exc=exc, countdown=countdown)