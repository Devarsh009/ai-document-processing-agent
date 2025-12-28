from app.workflows.graph import run_workflow
from app.workers.celery_app import celery_app

@celery_app.task(name="process_document_task")
def process_document_task(doc_id: str, file_path: str):
    print(f"[CELERY] Processing document {doc_id} from {file_path}")
    # Pass both ID and Path to the workflow
    return run_workflow(doc_id, file_path)