import os
import json
from crewai import Agent, Task, Crew, LLM

# 1. Setup LLM
def get_llm():
    return LLM(
        model="groq/llama-3.1-8b-instant",
        api_key=os.getenv("GROQ_API_KEY"),
        temperature=0.0
    )

# Helper to clean LLM output
def clean_and_parse_json(raw_output: str):
    try:
        # Remove code blocks if present
        clean_text = raw_output.replace("```json", "").replace("```", "").strip()
        return json.loads(clean_text)
    except json.JSONDecodeError:
        print(f"FAILED TO PARSE JSON. RAW OUTPUT: {raw_output}")
        # Return a fallback object so the pipeline doesn't crash
        return {"classification": "Unknown", "confidence": 0.0, "extracted_data": {}}

# 2. Classifier Agent
def run_classification_crew(doc_content: str):
    # Safety check for empty content
    if not doc_content or len(doc_content) < 5:
        return {"classification": "Unknown", "confidence": 0.0}

    llm = get_llm()
    
    classifier = Agent(
        role="Senior Document Classifier",
        goal="Classify documents strictly as JSON.",
        backstory="You are a machine that outputs only JSON. You never speak.",
        llm=llm,
        verbose=True
    )

    task = Task(
        description=f"""
        Analyze the text below. Determine if it is an 'Invoice', 'Contract', or 'Technical Spec'.
        
        RULES:
        1. Output MUST be valid JSON.
        2. No markdown formatting.
        3. No conversational text.
        
        TEXT TO ANALYZE:
        ----------------
        {doc_content[:3000]}
        ----------------
        """,
        expected_output='{"classification": "Invoice", "confidence": 0.98}',
        agent=classifier
    )

    crew = Crew(agents=[classifier], tasks=[task], verbose=True)
    result = str(crew.kickoff())
    
    return clean_and_parse_json(result)

# 3. Extractor Agent
def run_extraction_crew(doc_content: str, doc_type: str):
    llm = get_llm()

    extractor = Agent(
        role=f"{doc_type} Extractor",
        goal=f"Extract data from {doc_type}s as JSON.",
        backstory="You are a machine that outputs only JSON.",
        llm=llm,
        verbose=True
    )

    task = Task(
        description=f"""
        Extract key fields (like Total, Vendor, Dates, Parties) from the text below.
        
        RULES:
        1. Output MUST be valid JSON.
        2. Return strict key-value pairs.
        
        TEXT TO ANALYZE:
        ----------------
        {doc_content[:3000]}
        ----------------
        """,
        expected_output='{"total": 1000, "vendor": "Acme"}',
        agent=extractor
    )

    crew = Crew(agents=[extractor], tasks=[task], verbose=True)
    result = str(crew.kickoff())
    
    return clean_and_parse_json(result)

# 4. Manual Review Handler (Added)
def run_manual_review_crew(doc_content: str, confidence: float):
    # This simulates the manual review process.
    # In a real system, this might trigger an email alert or update a UI status.
    return {
        "status": "flagged_for_review",
        "reason": f"Low confidence score ({confidence})",
        "action_required": "Human verification needed"
    }