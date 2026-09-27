from app.agent.state import AgentState
from app.agent.tools.rag_tools import search_hr_knowledge
from app.agent.tools.hr_tools import (
    match_candidates,
    get_candidate_details,
    get_candidate_evidence,
    generate_interview_questions,
    generate_candidate_summary,
)
from app.agent.tools.action_tools import draft_candidate_email, send_candidate_email
from app.utils.logger import logger

def tool_execution_node(state: AgentState) -> AgentState:
    """Executes the tool selected during intent analysis."""
    intent = state.get("intent", "PLAYBOOK_QA")
    user_query = state.get("user_query", "")
    job_id = state.get("job_id") or "default_job_001"
    candidate_id = state.get("candidate_id") or "C001"
    
    logs = list(state.get("activity_logs", []))
    logger.info(f"LangGraph Node [tool_execution_node] executing intent: '{intent}'")
    
    tool_result = ""
    selected_tool = ""
    approval_required = False
    approval_status = state.get("approval_status", "none")

    if intent == "PLAYBOOK_QA":
        selected_tool = "search_hr_knowledge"
        logs.append({"step": "Tool Selection", "detail": "Selected tool: search_hr_knowledge"})
        tool_result = search_hr_knowledge.invoke({"query": user_query})

    elif intent == "CANDIDATE_MATCHING":
        selected_tool = "match_candidates"
        logs.append({"step": "Tool Selection", "detail": f"Selected tool: match_candidates for job {job_id}"})
        tool_result = match_candidates.invoke({"job_id": job_id})

    elif intent == "CANDIDATE_DETAILS":
        selected_tool = "get_candidate_details"
        logs.append({"step": "Tool Selection", "detail": f"Selected tool: get_candidate_details for {candidate_id}"})
        tool_result = get_candidate_details.invoke({"candidate_id": candidate_id})
        evidence_res = get_candidate_evidence.invoke({"candidate_id": candidate_id})
        tool_result += f"\n\n{evidence_res}"

    elif intent == "INTERVIEW_GEN":
        selected_tool = "generate_interview_questions"
        logs.append({"step": "Tool Selection", "detail": f"Selected tool: generate_interview_questions for {candidate_id}"})
        tool_result = generate_interview_questions.invoke({"job_id": job_id, "candidate_id": candidate_id})

    elif intent == "EMAIL_GEN":
        selected_tool = "draft_candidate_email"
        logs.append({"step": "Tool Selection", "detail": f"Selected tool: draft_candidate_email for {candidate_id}"})
        tool_result = draft_candidate_email.invoke({"candidate_id": candidate_id})
        logs.append({"step": "Email Drafted", "detail": "Draft created. Action requires HR Approval before sending."})

    elif intent == "HR_ACTION":
        selected_tool = "send_candidate_email"
        if approval_status == "approved":
            logs.append({"step": "Action Approved", "detail": "HR Approval granted. Dispatching email..."})
            tool_result = send_candidate_email.invoke({"recipient_email": f"{candidate_id}@example.com", "email_content": "Interview invitation"})
        elif approval_status == "rejected":
            logs.append({"step": "Action Rejected", "detail": "HR Approval rejected. Email dispatch cancelled."})
            tool_result = "ACTION CANCELLED: Human HR Administrator rejected the email send operation."
        else:
            selected_tool = "send_candidate_email"
            approval_required = True
            approval_status = "pending"
            logs.append({"step": "Approval Gate", "detail": "Sensitive Action Paused: Awaiting Human HR Approval."})
            tool_result = "PENDING APPROVAL: Email draft is ready. Please click 'Approve Action' in the UI to send."

    else:
        selected_tool = "search_hr_knowledge"
        logs.append({"step": "Tool Selection", "detail": "Defaulting to search_hr_knowledge"})
        tool_result = search_hr_knowledge.invoke({"query": user_query})

    logs.append({"step": "Tool Execution Complete", "detail": f"Tool '{selected_tool}' finished."})

    return {
        **state,
        "selected_tool": selected_tool,
        "tool_result": tool_result,
        "approval_required": approval_required,
        "approval_status": approval_status,
        "activity_logs": logs
    }
