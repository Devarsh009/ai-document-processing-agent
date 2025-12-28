import os
import shutil
import uuid
from fastapi import FastAPI, UploadFile, File
from app.workers.tasks import process_document_task

app = FastAPI()

# Create a directory to store uploaded files temporarily
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@app.post("/process")
async def process_document(file: UploadFile = File(...)):
    # 1. Generate a unique ID for the document
    doc_id = str(uuid.uuid4())
    
    # 2. Save the file locally so the worker can read it
    file_path = os.path.join(UPLOAD_DIR, f"{doc_id}_{file.filename}")
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # 3. Queue the task in Celery, passing the FILE PATH
    process_document_task.delay(doc_id, file_path)

    return {
        "status": "queued", 
        "doc_id": doc_id, 
        "filename": file.filename
    }