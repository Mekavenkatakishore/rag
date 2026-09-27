import json
from langchain_core.output_parsers import StrOutputParser

from app.agent.state import AgentState
from app.agent.prompts import INTENT_CLASSIFICATION_PROMPT
from app.agent.llm import get_llm
from app.utils.logger import logger

llm = get_llm(temperature=0.0)
chain = INTENT_CLASSIFICATION_PROMPT | llm | StrOutputParser()

def analyze_query_node(state: AgentState) -> AgentState:
    """Analyzes user query and determines intent, job_id, and candidate_id."""
    user_query = state.get("user_query", "")
    logger.info(f"LangGraph Node [analyze_query_node] processing: '{user_query[:60]}'")
    
    logs = list(state.get("activity_logs", []))
    logs.append({"step": "Query Analysis", "detail": f"Classifying intent for prompt: '{user_query[:40]}...'"})

    try:
        raw_res = chain.invoke({"user_query": user_query})
        clean_text = raw_res.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        parsed = json.loads(clean_text)
        
        intent = parsed.get("intent", "PLAYBOOK_QA")
        job_id = parsed.get("job_id") or state.get("job_id") or "default_job_001"
        candidate_id = parsed.get("candidate_id") or state.get("candidate_id")
        
        logs.append({"step": "Intent Classified", "detail": f"Intent: {intent} | Job: {job_id}"})
        
        return {
            **state,
            "intent": intent,
            "job_id": job_id,
            "candidate_id": candidate_id,
            "activity_logs": logs
        }
    except Exception as e:
        logger.error(f"Error in analyze_query_node: {e}")
        logs.append({"step": "Analysis Fallback", "detail": f"Defaulting to PLAYBOOK_QA due to parsing error."})
        return {
            **state,
            "intent": "PLAYBOOK_QA",
            "job_id": state.get("job_id") or "default_job_001",
            "activity_logs": logs
        }
