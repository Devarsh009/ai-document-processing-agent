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

def extract_node(state: dict):
    logger.info(f"--- EXTRACTING ({state['classification']}) ---")
    data = run_extraction_crew(state['content'], state['classification'])
    logger.info(f"Extraction complete: {data}")
    return {"extracted_data": data}

def manual_review_node(state: dict):
    logger.warning(f"--- LOW CONFIDENCE ({state['confidence_score']}) -> MANUAL REVIEW ---")
    return {
        "next_step": "manual_review",
        "validation_errors": ["Document confidence too low for auto-extraction"]
    }