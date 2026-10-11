import os
import uuid
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.config import settings
from app.storage.repository import create_job, update_job_status

client = TestClient(app)


def test_health_endpoints():
    for url in ("/health", "/v1/health"):
        response = client.get(url)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["app"] == "ai-document-processing-agent"


@patch("redis.Redis.from_url")
def test_readiness_endpoint_ready(mock_redis_cls):
    mock_r = MagicMock()
    mock_r.ping.return_value = True
    mock_redis_cls.return_value = mock_r

    response = client.get("/v1/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["broker"] is True
    assert data["database"] is True


@patch("app.main.process_document_task.apply_async")
def test_v1_submit_document_success(mock_apply_async):
    mock_apply_async.return_value = MagicMock(id="mock-task-id")

    files = {"file": ("invoice.txt", b"INVOICE #INV-101\nTotal: $500", "text/plain")}
    response = client.post("/v1/documents", files=files)
    assert response.status_code == 202
    data = response.json()
    assert data["status"] == "queued"
    assert data["filename"] == "invoice.txt"
    assert "id" in data
    assert f"/v1/documents/{data['id']}" in data["status_url"]
    mock_apply_async.assert_called_once()


@patch("app.main.process_document_task.apply_async")
def test_v1_submit_document_broker_failure(mock_apply_async):
    mock_apply_async.side_effect = Exception("Redis unreachable")

    files = {"file": ("contract.txt", b"Agreement between A and B", "text/plain")}
    response = client.post("/v1/documents", files=files)
    assert response.status_code == 503
    assert "Task broker (Redis) is currently unreachable" in response.json()["detail"]


def test_v1_submit_unsupported_extension():
    files = {"file": ("malicious.exe", b"MZ\x90\x00", "application/octet-stream")}
    response = client.post("/v1/documents", files=files)
    assert response.status_code == 415


def test_v1_submit_invalid_pdf_magic():
    files = {"file": ("fake.pdf", b"NOT_A_REAL_PDF", "application/pdf")}
    response = client.post("/v1/documents", files=files)
    assert response.status_code == 415


def test_v1_get_document_lifecycle():
    doc_id = str(uuid.uuid4())
    create_job(
        doc_id=doc_id,
        filename="test.txt",
        content_type="text/plain",
        file_size_bytes=100,
        file_path="uploads/test.txt",
        sha256_checksum="abc123hash",
        status="received",
        processing_stage="ingest",
    )

    # 1. Fetch document status
    res = client.get(f"/v1/documents/{doc_id}")
    assert res.status_code == 200
    assert res.json()["status"] == "received"

    # 2. Result endpoint before ready -> 409 Conflict
    res_not_ready = client.get(f"/v1/documents/{doc_id}/result")
    assert res_not_ready.status_code == 409

    # 3. Transition to succeeded
    update_job_status(doc_id, "queued")
    update_job_status(
        doc_id=doc_id,
        new_status="processing",
        processing_stage="extract",
    )
    update_job_status(
        doc_id=doc_id,
        new_status="succeeded",
        processing_stage="completed",
        classification="Invoice",
        confidence_score=0.95,
        extracted_data={"total_due": 500.0},
    )

    # 4. Result endpoint after completion -> 200 OK
    res_ready = client.get(f"/v1/documents/{doc_id}/result")
    assert res_ready.status_code == 200
    data = res_ready.json()
    assert data["status"] == "succeeded"
    assert data["classification"] == "Invoice"
    assert data["extracted_data"]["total_due"] == 500.0


def test_v1_review_workflow():
    doc_id = str(uuid.uuid4())
    create_job(
        doc_id=doc_id,
        filename="ambiguous.txt",
        content_type="text/plain",
        file_size_bytes=50,
        file_path="uploads/ambiguous.txt",
        sha256_checksum="def456hash",
        status="received",
        processing_stage="ingest",
    )

    # Transition to needs_review
    update_job_status(doc_id, "queued")
    update_job_status(doc_id, "processing")
    update_job_status(
        doc_id=doc_id,
        new_status="needs_review",
        processing_stage="review",
        classification="General_Correspondence",
        confidence_score=0.45,
        validation_errors=["Confidence below 0.70"],
    )

    # Submit human review override
    review_payload = {
        "action": "override",
        "notes": "Auditor verified as Invoice",
        "overrides": {"classification": "Invoice", "total_due": 350.0},
    }
    review_res = client.post(f"/v1/documents/{doc_id}/review", json=review_payload)
    assert review_res.status_code == 200
    rev_data = review_res.json()
    assert rev_data["status"] == "succeeded"
    assert rev_data["review_decision"]["action"] == "override"

    # Cannot review document once already in terminal succeeded state
    invalid_review = client.post(
        f"/v1/documents/{doc_id}/review", json={"action": "approve"}
    )
    assert invalid_review.status_code == 400


def test_legacy_backward_compatibility():
    # Test POST /process
    with patch("app.main.process_document_task.apply_async"):
        files = {"file": ("legacy.txt", b"Legacy file text", "text/plain")}
        res = client.post("/process", files=files)
        assert res.status_code == 200
        doc_id = res.json()["doc_id"]

        # Test GET /status/{doc_id}
        status_res = client.get(f"/status/{doc_id}")
        assert status_res.status_code == 200
        assert status_res.json()["doc_id"] == doc_id
