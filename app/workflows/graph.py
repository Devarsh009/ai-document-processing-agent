from langgraph.graph import StateGraph, END
from app.workflows.state import AgentState
from app.workflows.nodes import (
    ingest_document, 
    classify_node, 
    extract_node, 
    manual_review_node,
    validate_node,
    route_document
)

# --- Logic for Validation Routing ---
def route_validation(state):
    """
    Decides where to go after Validation.
    If there are errors -> Manual Review.
    Else -> End.
    """
    errors = state.get("validation_errors", [])
    if errors and len(errors) > 0:
        return "manual_review"
    return "end"

# --- Build the Graph ---
def run_workflow(doc_id: str, file_path: str):
    workflow = StateGraph(AgentState)

    # 1. Add Nodes
    workflow.add_node("ingest", ingest_document)
    workflow.add_node("classify", classify_node)
    workflow.add_node("extract", extract_node)
    workflow.add_node("validate", validate_node)       # <--- NEW NODE
    workflow.add_node("manual_review", manual_review_node)

    # 2. Set Entry Point
    workflow.set_entry_point("ingest")

    # 3. Define Edges
    
    # Ingest -> Classify
    workflow.add_edge("ingest", "classify")

    # Classify -> (Extract OR Manual Review)
    workflow.add_conditional_edges(
        "classify",
        route_document,
        {
            "extract": "extract",
            "manual_review": "manual_review"
        }
    )

    # Extract -> Validate (The fix for "Quality Assurance")
    workflow.add_edge("extract", "validate")

    # Validate -> (Manual Review OR End)
    workflow.add_conditional_edges(
        "validate",
        route_validation,
        {
            "manual_review": "manual_review",
            "end": END
        }
    )

    # Manual Review -> End
    workflow.add_edge("manual_review", END)

    # 4. Compile
    app = workflow.compile()
    
    initial_state = {
        "doc_id": doc_id,
        "file_path": file_path,
        "content": "",
        "classification": None,
        "confidence_score": 0.0,
        "extracted_data": {},
        "validation_errors": [],
        "next_step": None
    }
    
    return app.invoke(initial_state)