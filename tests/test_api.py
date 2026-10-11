import os
import uuid
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.config import settings

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["app"] == "ai-document-processing-agent"


@patch("app.main.process_document_task.apply_async")
def test_process_document_success(mock_apply_async):
    mock_apply_async.return_value = MagicMock(id="mock-task-id")

    files = {"file": ("invoice.txt", b"INVOICE #123\nTotal: $100", "text/plain")}
    response = client.post("/process", files=files)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "queued"
    assert data["filename"] == "invoice.txt"
    assert "doc_id" in data
    # Verify doc_id is valid UUID
    uuid.UUID(data["doc_id"])
    mock_apply_async.assert_called_once()


@patch("app.main.process_document_task.apply_async")
def test_process_document_broker_failure(mock_apply_async):
    mock_apply_async.side_effect = Exception("Redis connection refused")

    files = {"file": ("contract.txt", b"Contract text", "text/plain")}
    response = client.post("/process", files=files)
    assert response.status_code == 503
    assert "Task broker (Redis) is currently unreachable" in response.json()["detail"]


def test_status_invalid_uuid():
    response = client.get("/status/invalid-uuid-123")
    assert response.status_code == 400
    assert "Invalid doc_id format" in response.json()["detail"]


@patch("app.main.celery_app.AsyncResult")
def test_status_not_found(mock_async_result):
    random_id = str(uuid.uuid4())
    mock_task = MagicMock()
    mock_task.state = "PENDING"
    mock_task.ready.return_value = False
    mock_async_result.return_value = mock_task

    # When no file exists on disk and task is PENDING, should return 404
    response = client.get(f"/status/{random_id}")
    assert response.status_code == 404
    assert f"Document with ID '{random_id}' not found." in response.json()["detail"]


@patch("app.main.celery_app.AsyncResult")
def test_status_completed(mock_async_result):
    test_id = str(uuid.uuid4())
    mock_task = MagicMock()
    mock_task.state = "SUCCESS"
    mock_task.result = {
        "doc_id": test_id,
        "classification": "Invoice",
        "confidence_score": 0.95,
        "extracted_data": {"total_due": 8250.0},
        "validation_errors": [],
    }
    mock_async_result.return_value = mock_task

    response = client.get(f"/status/{test_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["doc_id"] == test_id
    assert data["status"] == "completed"
    assert data["result"]["classification"] == "Invoice"


@patch("app.main.celery_app.AsyncResult")
def test_status_failed(mock_async_result):
    test_id = str(uuid.uuid4())
    mock_task = MagicMock()
    mock_task.state = "FAILURE"
    mock_async_result.return_value = mock_task

    response = client.get(f"/status/{test_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["doc_id"] == test_id
    assert data["status"] == "failed"
    assert "Document processing failed" in data["error"]


@patch("app.main.celery_app.AsyncResult")
def test_status_processing(mock_async_result):
    test_id = str(uuid.uuid4())
    mock_task = MagicMock()
    mock_task.state = "STARTED"
    mock_async_result.return_value = mock_task

    response = client.get(f"/status/{test_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["doc_id"] == test_id
    assert data["status"] == "processing"
