DOCUMENT_STATE = {}

def save_state(doc_id: str, data: dict):
    DOCUMENT_STATE[doc_id] = data

def get_state(doc_id: str):
    return DOCUMENT_STATE.get(doc_id)
