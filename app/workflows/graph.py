from langgraph.graph import StateGraph, END
from app.workflows.state import AgentState
from app.workflows.nodes import (
    ingest_document,
    classify_node,
    extract_node,
    manual_review_node,
    validate_node,
    route_document,
)


def route_validation(state: dict) -> str:
    """
    Decides where to go after validation:
    - If validation errors exist -> route to manual_review.
    - Otherwise -> complete workflow (end).
    """
    errors = state.get("validation_errors", [])
    if errors and len(errors) > 0:
        return "manual_review"
    return "end"


def build_workflow():
    """Builds and compiles the LangGraph StateGraph workflow."""
    workflow = StateGraph(AgentState)

    # 1. Add Nodes
    workflow.add_node("ingest", ingest_document)
    workflow.add_node("classify", classify_node)
    workflow.add_node("extract", extract_node)
    workflow.add_node("validate", validate_node)
    workflow.add_node("manual_review", manual_review_node)

    # 2. Set Entry Point
    workflow.set_entry_point("ingest")

    # 3. Define Edges
    workflow.add_edge("ingest", "classify")

    workflow.add_conditional_edges(
        "classify",
        route_document,
        {
            "extract": "extract",
            "manual_review": "manual_review",
        },
    )

    workflow.add_edge("extract", "validate")

    workflow.add_conditional_edges(
        "validate",
        route_validation,
        {
            "manual_review": "manual_review",
            "end": END,
        },
    )

    workflow.add_edge("manual_review", END)

    return workflow.compile()


def run_workflow(doc_id: str, file_path: str) -> dict:
    """Executes the document processing workflow for a given document."""
    app = build_workflow()

    initial_state = {
        "doc_id": doc_id,
        "file_path": file_path,
        "content": "",
        "classification": None,
        "confidence_score": 0.0,
        "extracted_data": {},
        "validation_errors": [],
        "next_step": None,
    }

    return app.invoke(initial_state)