from typing import TypedDict, Optional, Dict, Any, List

class AgentState(TypedDict):
    doc_id: str
    file_path: str    # <--- NEW FIELD
    content: str
    classification: Optional[str]
    confidence_score: float
    extracted_data: Dict[str, Any]
    validation_errors: List[str]
    next_step: Optional[str]