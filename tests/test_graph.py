import os
import tempfile
from unittest.mock import patch
from app.workflows.graph import run_workflow


@patch("app.workflows.nodes.run_extraction_crew")
@patch("app.workflows.nodes.run_classification_crew")
def test_workflow_successful_invoice(mock_classify, mock_extract):
    mock_classify.return_value = {"classification": "Invoice", "confidence": 0.95}
    mock_extract.return_value = {
        "subtotal": 7500.0,
        "tax": 750.0,
        "total_due": 8250.0,
        "vendor": "CloudCompute Inc.",
    }

    with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".txt", encoding="utf-8") as tf:
        tf.write("INVOICE #INV-2024-001\nSubtotal: $7,500.00\nTax: $750.00\nTotal Due: $8,250.00")
        temp_path = tf.name

    try:
        result = run_workflow("doc-1", temp_path)
        assert result["classification"] == "Invoice"
        assert result["confidence_score"] == 0.95
        assert result["extracted_data"]["vendor"] == "CloudCompute Inc."
        assert result["validation_errors"] == []
        assert result["next_step"] is None  # Completed without routing to manual review
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


@patch("app.workflows.nodes.run_classification_crew")
def test_workflow_low_confidence_routes_to_manual_review(mock_classify):
    mock_classify.return_value = {
        "classification": "General_Correspondence",
        "confidence": 0.40,
    }

    with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".txt", encoding="utf-8") as tf:
        tf.write("Subject: Hello team, please see attached invoice discussion.")
        temp_path = tf.name

    try:
        result = run_workflow("doc-2", temp_path)
        assert result["classification"] == "General_Correspondence"
        assert result["confidence_score"] == 0.40
        assert result["next_step"] == "manual_review"
        assert len(result["validation_errors"]) > 0
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


@patch("app.workflows.nodes.run_extraction_crew")
@patch("app.workflows.nodes.run_classification_crew")
def test_workflow_invoice_math_failure_routes_to_manual_review(mock_classify, mock_extract):
    mock_classify.return_value = {"classification": "Invoice", "confidence": 0.90}
    mock_extract.return_value = {
        "subtotal": 1000.0,
        "tax": 100.0,
        "total_due": 2000.0,  # Mismatch: 1000 + 100 != 2000
    }

    with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".txt", encoding="utf-8") as tf:
        tf.write("INVOICE with bad math")
        temp_path = tf.name

    try:
        result = run_workflow("doc-3", temp_path)
        assert result["classification"] == "Invoice"
        assert result["next_step"] == "manual_review"
        assert any("Math Mismatch" in err for err in result["validation_errors"])
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)
