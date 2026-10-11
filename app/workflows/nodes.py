import os
import re
from typing import Any
from app.agents.crew_runner import run_classification_crew, run_extraction_crew
from app.config import settings
from app.parsers.document_parser import parse_document, DocumentParsingError, UnsupportedFileTypeError
from app.utils.logger import get_logger

logger = get_logger(__name__)


def ingest_document(state: dict) -> dict:
    """
    Reads and parses the document using the multi-format DocumentParser.
    Supports TXT, text-based PDF, and DOCX.
    """
    file_path = state.get("file_path", "")
    logger.info(f"Ingesting file: {file_path}")

    if not file_path or not os.path.exists(file_path):
        logger.error(f"File not found: {file_path}")
        return {
            "content": "",
            "page_count": 0,
            "format": "unknown",
            "validation_errors": [f"File not found: {file_path}"],
        }

    try:
        parsed = parse_document(file_path)
        logger.info(
            f"Successfully parsed {parsed.format} ({parsed.page_count} pages, {len(parsed.text)} characters)."
        )

        validation_errors = list(state.get("validation_errors", []))
        if parsed.is_scanned_or_empty:
            error_msg = (
                "File is empty or contains no extractable text. Scanned PDFs/images and OCR are unsupported."
            )
            logger.warning(error_msg)
            validation_errors.append(error_msg)

        return {
            "content": parsed.text,
            "page_count": parsed.page_count,
            "format": parsed.format,
            "validation_errors": validation_errors,
        }
    except (DocumentParsingError, UnsupportedFileTypeError) as e:
        logger.error(f"Parsing error for {file_path}: {e}")
        return {
            "content": "",
            "page_count": 0,
            "format": "unknown",
            "validation_errors": [f"Parsing error: {str(e)}"],
        }
    except Exception as e:
        logger.error(f"Unexpected error ingesting {file_path}: {e}")
        return {
            "content": "",
            "page_count": 0,
            "format": "unknown",
            "validation_errors": [f"Unexpected ingestion error: {str(e)}"],
        }


def classify_node(state: dict) -> dict:
    """Classifies document content using LLM agent."""
    content = state.get("content", "")
    if not content or len(content.strip()) < 5:
        logger.warning("Empty or insufficient content; assigning Unknown classification.")
        return {
            "classification": "Unknown",
            "confidence_score": 0.0,
        }

    logger.info("Classifying document content...")
    result = run_classification_crew(content)
    logger.info(f"Classification result: {result}")

    raw_conf = result.get("confidence", 0.0)
    try:
        confidence = float(raw_conf) if raw_conf is not None else 0.0
    except (ValueError, TypeError):
        confidence = 0.0

    return {
        "classification": result.get("classification", "Unknown"),
        "confidence_score": confidence,
    }


def route_document(state: dict) -> str:
    """
    Determines next workflow step based on classification confidence.
    Routes to manual_review if confidence is below threshold.
    """
    classification = state.get("classification")
    confidence = state.get("confidence_score", 0.0)
    threshold = settings.CONFIDENCE_THRESHOLD

    logger.info(f"Routing check: Type={classification}, Confidence={confidence}, Threshold={threshold}")

    if confidence < threshold:
        logger.warning(f"Low confidence ({confidence} < {threshold}) -> routing to manual review.")
        return "manual_review"

    return "extract"


def extract_node(state: dict) -> dict:
    """Extracts structured key-value data using the specialized extractor agent."""
    classification = state.get("classification") or "Document"
    content = state.get("content", "")
    logger.info(f"Extracting fields for {classification}...")
    data = run_extraction_crew(content, classification)
    if not isinstance(data, dict):
        data = {}
    logger.info(f"Extraction complete: {data}")
    return {"extracted_data": data}


def _parse_numeric(val: Any) -> float:
    """Helper to safely parse currency strings or numbers to float."""
    if val is None:
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        cleaned = re.sub(r"[^\d.-]", "", val.strip())
        if cleaned:
            return float(cleaned)
    raise ValueError(f"Cannot parse numeric value from '{val}'")


def validate_node(state: dict) -> dict:
    """
    Deterministic rule-based validation of extracted data.
    Validates arithmetic consistency for invoices (subtotal + tax == total).
    """
    logger.info("Validating extracted data...")
    data = state.get("extracted_data", {})
    classification = state.get("classification")
    validation_errors = list(state.get("validation_errors", []))

    if not data:
        validation_errors.append("No data extracted")
        return {"validation_errors": validation_errors}

    # Invoice specific validation: check arithmetic
    if classification == "Invoice":
        try:
            subtotal = _parse_numeric(data.get("subtotal", 0.0))
            tax = _parse_numeric(data.get("tax", 0.0))
            total_val = data.get("total_due") if "total_due" in data else data.get("total", 0.0)
            total = _parse_numeric(total_val)

            calculated_total = subtotal + tax
            if abs(calculated_total - total) > 0.01:
                error_msg = f"Math Mismatch: Subtotal ({subtotal}) + Tax ({tax}) != Total ({total})"
                logger.error(f"[ERROR] {error_msg}")
                validation_errors.append(error_msg)
            else:
                logger.info("[OK] Math Validation Passed")

        except ValueError as e:
            error_msg = f"Invalid number format in extracted data: {str(e)}"
            logger.error(f"[ERROR] {error_msg}")
            validation_errors.append(error_msg)

    return {"validation_errors": validation_errors}


def manual_review_node(state: dict) -> dict:
    """Flags the document for human review and documents reason."""
    confidence = state.get("confidence_score", 0.0)
    errors = state.get("validation_errors", [])

    if errors:
        logger.warning(f"Manual review triggered. Validation errors: {errors}")
    else:
        logger.warning(f"Manual review triggered. Low confidence ({confidence})")

    fallback_errors = errors if errors else [f"Confidence ({confidence}) below threshold ({settings.CONFIDENCE_THRESHOLD})"]

    return {
        "next_step": "manual_review",
        "validation_errors": fallback_errors,
    }