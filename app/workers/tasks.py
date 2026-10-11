from app.workflows.graph import run_workflow
from app.workers.celery_app import celery_app
from app.utils.logger import get_logger

logger = get_logger(__name__)


@celery_app.task(name="process_document_task", bind=True)
def process_document_task(self, doc_id: str, file_path: str):
    """
    Celery background worker task to run the LangGraph processing workflow.
    Returns the final workflow state dictionary.
    """
    logger.info(f"[CELERY] Starting task {self.request.id} for document {doc_id} from {file_path}")
    try:
        result = run_workflow(doc_id, file_path)
        logger.info(f"[CELERY] Successfully completed document {doc_id}")
        return result
    except Exception as exc:
        logger.exception(f"[CELERY] Failed processing document {doc_id}: {exc}")
        raise exc