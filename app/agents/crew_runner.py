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

# 2. Classifier Agent (The Smart Version)
def run_classification_crew(doc_content: str):
    # Safety check for empty content
    if not doc_content or len(doc_content) < 5:
        return {"classification": "Unknown", "confidence": 0.0}

    llm = get_llm()
    
    classifier = Agent(
        role="Senior Document Classifier",
        # LEVEL 2 UPGRADE: The "Skeptical Auditor" Goal
        goal="""
        Accurately classify documents. 
        CRITICAL RULE: You are a Skeptical Auditor. 
        If a document looks like a casual email, a discussion about a document, or a mix of topics, 
        you MUST NOT classify it as a specific business document. 
        Instead, classify it as 'Other' or 'General_Correspondence' and assign a confidence score of 0.5 or lower.
        """,
        backstory="You are a machine that outputs only JSON. You never speak. You are extremely strict.",
        llm=llm,
        verbose=True
    )

    # LEVEL 1 UPGRADE: Chain of Thought Prompt
    task = Task(
        description=f"""
        Analyze the text below step-by-step to determine if it is an 'Invoice', 'Contract', or 'Technical Spec'.
        
        ANALYSIS STEPS:
        1. **Scan for key indicators**: Look for explicit headers like "INVOICE #", "AGREEMENT", or technical specs.
        2. **Check for ambiguity**: Does the text mention multiple types? (e.g., an email *discussing* a contract).
        3. **Verify structure**: A real Invoice must have line items and a total. A real Contract must have signatures or clauses.
        4. **Decision**:
           - If it is just an email *discussing* these topics, classify as "General_Correspondence".
           - ONLY classify as "Invoice" if it is the *actual document* itself.
           - If you are unsure, output a low confidence score (below 0.6).

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

# 4. Manual Review Handler
def run_manual_review_crew(doc_content: str, confidence: float):
    # This simulates the manual review process.
    return {
        "status": "flagged_for_review",
        "reason": f"Low confidence score ({confidence})",
        "action_required": "Human verification needed"
    }