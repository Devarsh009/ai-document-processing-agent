import os
from app.agents.crew_runner import run_classification_crew, run_extraction_crew, run_manual_review_crew
from app.utils.logger import get_logger

logger = get_logger(__name__)

def ingest_document(state: dict):
    file_path = state["file_path"]
    logger.info(f"Ingesting file: {file_path}")
    
    content = ""
    
    if not os.path.exists(file_path):
        logger.error(f"File not found: {file_path}")
        return {"content": ""}

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
            logger.info(f"Read {len(content)} characters.")
    except Exception as e:
        logger.error(f"Error reading file: {e}")
        
    return {"content": content}

def classify_node(state: dict):
    logger.info("--- CLASSIFYING ---")
    result = run_classification_crew(state['content'])
    logger.info(f"Classification result: {result}")
    return {
        "classification": result.get("classification"),
        "confidence_score": result.get("confidence")
    }

def route_document(state):
    """
    Determines the next step based on classification confidence.
    Used by the Conditional Edge in the Graph.
    """
    classification = state.get("classification")
    confidence = state.get("confidence_score", 0.0)
    
    logger.info(f"-> ROUTING: Type={classification}, Confidence={confidence}")

    # PRODUCTION LOGIC
    # If the AI is less than 70% sure, send to review.
    # This catches the ambiguous emails (which usually score ~0.2).
    if confidence < 0.70:
        logger.warning(f"--- LOW CONFIDENCE ({confidence}) -> MANUAL REVIEW ---")
        return "manual_review"
    
    return "extract"

def extract_node(state: dict):
    logger.info(f"--- EXTRACTING ({state['classification']}) ---")
    data = run_extraction_crew(state['content'], state['classification'])
    logger.info(f"Extraction complete: {data}")
    return {"extracted_data": data}

def validate_node(state: dict):
    """
    Deterministic Python validation to satisfy QA requirements.
    Checks consistency of extracted data (e.g. Math).
    """
    logger.info("--- VALIDATING DATA ---")
    data = state.get("extracted_data", {})
    classification = state.get("classification")
    validation_errors = []

    if not data:
        return {"validation_errors": ["No data extracted"]}

    # Specific Rule for Invoices: Check Math
    if classification == "Invoice":
        try:
            # Safely get values, defaulting to 0.0 if missing
            subtotal = float(data.get("subtotal", 0.0) or 0.0)
            tax = float(data.get("tax", 0.0) or 0.0)
            total = float(data.get("total_due", 0.0) or 0.0)

            # Check math with a small tolerance for floating point rounding
            calculated_total = subtotal + tax
            if abs(calculated_total - total) > 0.01:
                error_msg = f"Math Mismatch: Subtotal ({subtotal}) + Tax ({tax}) != Total ({total})"
                logger.error(f"❌ {error_msg}")
                validation_errors.append(error_msg)
            else:
                logger.info("✅ Math Validation Passed")

        except ValueError:
            error_msg = "Invalid number format in extracted data"
            logger.error(error_msg)
            validation_errors.append(error_msg)
    
    # If errors exist, we will route to manual review next
    if validation_errors:
        return {"validation_errors": validation_errors}
    
    return {"validation_errors": []}

def manual_review_node(state: dict):
    # Logs why it ended up here
    confidence = state.get("confidence_score")
    errors = state.get("validation_errors", [])
    
    if errors:
        logger.warning(f"--- MANUAL REVIEW TRIGGERED: Validation Errors: {errors} ---")
    else:
        logger.warning(f"--- MANUAL REVIEW TRIGGERED: Low Confidence ({confidence}) ---")
        
    return {
        "next_step": "manual_review",
        # Ensure validation errors are persisted if they exist
        "validation_errors": errors if errors else ["Document confidence too low"]
    }