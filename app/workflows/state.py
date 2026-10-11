from typing import Any, Dict, List, Optional, TypedDict


class AgentState(TypedDict):
    doc_id: str
    file_path: str
    content: str
    page_count: int
    format: str
    classification: Optional[str]
    confidence_score: float
    extracted_data: Dict[str, Any]
    validation_errors: List[str]
    next_step: Optional[str]