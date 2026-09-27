from app.agent.tools.rag_tools import search_hr_knowledge
from app.agent.tools.hr_tools import (
    match_candidates,
    get_candidate_details,
    get_candidate_evidence,
    generate_interview_questions,
    generate_candidate_summary,
)
from app.agent.tools.action_tools import draft_candidate_email, send_candidate_email

ALL_AGENT_TOOLS = [
    search_hr_knowledge,
    match_candidates,
    get_candidate_details,
    get_candidate_evidence,
    generate_interview_questions,
    generate_candidate_summary,
    draft_candidate_email,
    send_candidate_email,
]

__all__ = [
    "search_hr_knowledge",
    "match_candidates",
    "get_candidate_details",
    "get_candidate_evidence",
    "generate_interview_questions",
    "generate_candidate_summary",
    "draft_candidate_email",
    "send_candidate_email",
    "ALL_AGENT_TOOLS",
]
