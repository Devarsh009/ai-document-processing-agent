import os
import tempfile
from unittest.mock import patch
import pytest

from app.workflows.nodes import (
    ingest_document,
    classify_node,
    route_document,
    extract_node,
    validate_node,
    manual_review_node,
    _parse_numeric,
)
from app.workflows.graph import route_validation


def test_ingest_document_missing_file():
    state = {"file_path": "non_existent_file_path_123.txt"}
    res = ingest_document(state)
    assert res["content"] == ""
    assert any("File not found" in err for err in res["validation_errors"])


def test_ingest_document_empty_file():
    with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".txt") as tf:
        tf.write("")
        temp_path = tf.name

    try:
        state = {"file_path": temp_path}
        res = ingest_document(state)
        assert res["content"] == ""
        assert any("File is empty" in err for err in res["validation_errors"])
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def test_ingest_document_success():
    with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".txt", encoding="utf-8") as tf:
        tf.write("Sample invoice text")
        temp_path = tf.name

    try:
        state = {"file_path": temp_path}
        res = ingest_document(state)
        assert res["content"] == "Sample invoice text"
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def test_classify_node_empty_content():
    state = {"content": ""}
    res = classify_node(state)
    assert res["classification"] == "Unknown"
    assert res["confidence_score"] == 0.0


@patch("app.workflows.nodes.run_classification_crew")
def test_classify_node_with_mocked_llm(mock_crew):
    mock_crew.return_value = {"classification": "Invoice", "confidence": 0.95}
    state = {"content": "INVOICE #123\nTotal: $500"}
    res = classify_node(state)
    assert res["classification"] == "Invoice"
    assert res["confidence_score"] == 0.95


def test_route_document_high_confidence():
    state = {"classification": "Invoice", "confidence_score": 0.85}
    assert route_document(state) == "extract"


def test_route_document_low_confidence():
    state = {"classification": "General_Correspondence", "confidence_score": 0.45}
    assert route_document(state) == "manual_review"


@patch("app.workflows.nodes.run_extraction_crew")
def test_extract_node(mock_crew):
    mock_crew.return_value = {
        "subtotal": 100.0,
        "tax": 10.0,
        "total_due": 110.0,
        "vendor": "Acme",
    }
    state = {"content": "Sample content", "classification": "Invoice"}
    res = extract_node(state)
    assert res["extracted_data"]["vendor"] == "Acme"
    assert res["extracted_data"]["total_due"] == 110.0


def test_parse_numeric_helper():
    assert _parse_numeric(100) == 100.0
    assert _parse_numeric(99.5) == 99.5
    assert _parse_numeric("$1,250.50") == 1250.50
    assert _parse_numeric("€ 300.00") == 300.00
    assert _parse_numeric(None) == 0.0
    with pytest.raises(ValueError):
        _parse_numeric("not_a_number")


def test_validate_node_invoice_math_passed():
    state = {
        "classification": "Invoice",
        "extracted_data": {
            "subtotal": 7500.0,
            "tax": 750.0,
            "total_due": 8250.0,
        },
        "validation_errors": [],
    }
    res = validate_node(state)
    assert res["validation_errors"] == []


def test_validate_node_invoice_math_with_currency_strings():
    state = {
        "classification": "Invoice",
        "extracted_data": {
            "subtotal": "$7,500.00",
            "tax": "$750.00",
            "total_due": "$8,250.00",
        },
        "validation_errors": [],
    }
    res = validate_node(state)
    assert res["validation_errors"] == []


def test_validate_node_invoice_math_mismatch():
    state = {
        "classification": "Invoice",
        "extracted_data": {
            "subtotal": 500.0,
            "tax": 50.0,
            "total_due": 600.0,  # Expected 550.0
        },
        "validation_errors": [],
    }
    res = validate_node(state)
    assert len(res["validation_errors"]) == 1
    assert "Math Mismatch" in res["validation_errors"][0]


def test_validate_node_contract_passes():
    state = {
        "classification": "Contract",
        "extracted_data": {
            "parties": ["Alpha", "Beta"],
            "fee": 400.0,
        },
        "validation_errors": [],
    }
    res = validate_node(state)
    assert res["validation_errors"] == []


def test_route_validation():
    assert route_validation({"validation_errors": []}) == "end"
    assert route_validation({"validation_errors": ["Some error"]}) == "manual_review"


def test_manual_review_node():
    state = {
        "confidence_score": 0.4,
        "validation_errors": ["Ambiguous email"],
    }
    res = manual_review_node(state)
    assert res["next_step"] == "manual_review"
    assert "Ambiguous email" in res["validation_errors"]
