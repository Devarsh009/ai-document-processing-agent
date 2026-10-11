import pytest
from app.agents.crew_runner import clean_and_parse_json, run_classification_crew, run_manual_review_crew


def test_clean_and_parse_json_valid():
    raw = '{"classification": "Invoice", "confidence": 0.95}'
    parsed = clean_and_parse_json(raw)
    assert parsed["classification"] == "Invoice"
    assert parsed["confidence"] == 0.95


def test_clean_and_parse_json_with_markdown_fences():
    raw = """```json
    {
        "classification": "Contract",
        "confidence": 0.88,
        "parties": ["Acme", "Beta"]
    }
    ```"""
    parsed = clean_and_parse_json(raw)
    assert parsed["classification"] == "Contract"
    assert parsed["confidence"] == 0.88
    assert parsed["parties"] == ["Acme", "Beta"]


def test_clean_and_parse_json_with_conversational_wrapping():
    raw = """Here is the result of my analysis:
    {"classification": "Technical Spec", "confidence": 0.75}
    Hope this helps!"""
    parsed = clean_and_parse_json(raw)
    assert parsed["classification"] == "Technical Spec"
    assert parsed["confidence"] == 0.75


def test_clean_and_parse_json_malformed():
    raw = "This is not json at all, totally invalid."
    parsed = clean_and_parse_json(raw)
    assert parsed["classification"] == "Unknown"
    assert parsed["confidence"] == 0.0
    assert parsed["extracted_data"] == {}


def test_clean_and_parse_json_empty_or_none():
    assert clean_and_parse_json("")["confidence"] == 0.0
    assert clean_and_parse_json(None)["confidence"] == 0.0


def test_run_classification_crew_short_content():
    # Documents shorter than 5 chars are rejected without calling LLM
    result = run_classification_crew("Hi")
    assert result["classification"] == "Unknown"
    assert result["confidence"] == 0.0


def test_run_manual_review_crew():
    result = run_manual_review_crew("ambiguous content", 0.45)
    assert result["status"] == "flagged_for_review"
    assert "0.45" in result["reason"]
