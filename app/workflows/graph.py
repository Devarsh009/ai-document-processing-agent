from langgraph.graph import StateGraph, END
from app.workflows.state import AgentState
from app.workflows.nodes import (
    ingest_document, 
    classify_node, 
    extract_node, 
    manual_review_node # <--- Import new node
)

# --- 1. Define the Logic Function ---
def route_document(state: AgentState):
    classification = state.get("classification")
    confidence = state.get("confidence_score", 0.0)
    
    print(f"-> ROUTING: Type={classification}, Confidence={confidence}")

    # ROUTING LOGIC:
    if confidence < 0.70:
        return "manual_review"
    else:
        return "extract"

# --- 2. Build the Graph ---
def run_workflow(doc_id: str, file_path: str):
    workflow = StateGraph(AgentState)

    # Add Nodes
    workflow.add_node("ingest", ingest_document)
    workflow.add_node("classify", classify_node)
    workflow.add_node("extract", extract_node)
    workflow.add_node("manual_review", manual_review_node) # <--- New Node

    # Set Entry Point
    workflow.set_entry_point("ingest")

    # Standard Edge
    workflow.add_edge("ingest", "classify")

    # --- CONDITIONAL EDGE ---
    # From 'classify', we decide where to go based on the 'route_document' function
    workflow.add_conditional_edges(
        "classify",
        route_document,
        {
            "extract": "extract",
            "manual_review": "manual_review"
        }
    )

    # Final Edges
    workflow.add_edge("extract", END)
    workflow.add_edge("manual_review", END)

    # Compile
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