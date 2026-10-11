import uuid
import pytest
from app.storage.repository import (
    create_job,
    get_job,
    update_job_status,
    record_review_decision,
    check_storage_health,
)


def test_storage_health():
    assert check_storage_health() is True


def test_job_crud_lifecycle():
    doc_id = str(uuid.uuid4())
    job = create_job(
        doc_id=doc_id,
        filename="invoice.txt",
        content_type="text/plain",
        file_size_bytes=2048,
        file_path="uploads/test.txt",
        sha256_checksum="dummy_checksum_123",
        status="received",
    )
    assert job["id"] == doc_id
    assert job["status"] == "received"

    # Legal transition: received -> queued
    updated = update_job_status(doc_id, "queued")
    assert updated["status"] == "queued"

    # Legal transition: queued -> processing
    updated = update_job_status(doc_id, "processing", processing_stage="extract")
    assert updated["status"] == "processing"
    assert updated["processing_stage"] == "extract"

    # Legal transition: processing -> needs_review
    updated = update_job_status(
        doc_id=doc_id,
        new_status="needs_review",
        validation_errors=["Confidence too low"],
    )
    assert updated["status"] == "needs_review"
    assert "Confidence too low" in updated["validation_errors"]


def test_illegal_state_transition():
    doc_id = str(uuid.uuid4())
    create_job(
        doc_id=doc_id,
        filename="illegal.txt",
        content_type="text/plain",
        file_size_bytes=100,
        file_path="uploads/illegal.txt",
        sha256_checksum="checksum_abc",
        status="received",
    )

    # received cannot jump straight to succeeded without queued/processing
    with pytest.raises(ValueError) as exc_info:
        update_job_status(doc_id, "succeeded")
    assert "Illegal state transition" in str(exc_info.value)


def test_record_review_actions():
    doc_id = str(uuid.uuid4())
    create_job(
        doc_id=doc_id,
        filename="review.txt",
        content_type="text/plain",
        file_size_bytes=100,
        file_path="uploads/review.txt",
        sha256_checksum="checksum_rev",
        status="received",
    )
    update_job_status(doc_id, "queued")
    update_job_status(doc_id, "processing")
    update_job_status(doc_id, "needs_review")

    # Action: reject
    rejected = record_review_decision(doc_id, action="reject", notes="Spam correspondence")
    assert rejected["status"] == "rejected"
    assert rejected["review_decision"]["action"] == "reject"
    assert rejected["review_decision"]["notes"] == "Spam correspondence"
