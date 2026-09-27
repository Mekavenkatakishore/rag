from fastapi import APIRouter, HTTPException, Depends
from app.schemas.agent_schemas import (
    AgentChatRequest,
    AgentApproveRequest,
    AgentRejectRequest,
    AgentChatResponse,
)
from app.agent.graph import agent_graph
from app.api.deps import get_current_user
from app.utils.logger import logger

router = APIRouter()

@router.post("/chat", response_model=AgentChatResponse)
async def agent_chat(req: AgentChatRequest, current_user: dict = Depends(get_current_user)):
    """
    Submits user prompt to the LangGraph Agentic AI HR Assistant.
    Maintains session state via thread_id checkpointer.
    """
    thread_id = req.thread_id or f"user_{current_user.get('id', 1)}_default"
    logger.info(f"Agent Chat request by user '{current_user['username']}' [thread_id: {thread_id}] | prompt: '{req.prompt[:60]}'")
    
    config = {"configurable": {"thread_id": thread_id}}
    initial_state = {
        "user_query": req.prompt,
        "messages": [("user", req.prompt)],
        "job_id": req.job_id or "default_job_001",
        "candidate_id": req.candidate_id,
        "approval_required": False,
        "approval_status": "none",
        "activity_logs": []
    }
    
    try:
        final_state = agent_graph.invoke(initial_state, config=config)
        return {
            "thread_id": thread_id,
            "intent": final_state.get("intent", "GENERAL"),
            "response": final_state.get("final_response", ""),
            "approval_required": final_state.get("approval_required", False),
            "approval_status": final_state.get("approval_status", "none"),
            "activity_logs": final_state.get("activity_logs", [])
        }
    except Exception as e:
        logger.error(f"Error executing agent chat graph: {e}")
        raise HTTPException(status_code=500, detail=f"Agent execution error: {e}")

@router.post("/approve", response_model=AgentChatResponse)
async def agent_approve(req: AgentApproveRequest, current_user: dict = Depends(get_current_user)):
    """Resumes paused agent workflow after Human HR Approval."""
    thread_id = req.thread_id
    logger.info(f"Agent Action APPROVED by HR user '{current_user['username']}' [thread_id: {thread_id}]")
    
    config = {"configurable": {"thread_id": thread_id}}
    update_state = {
        "intent": "HR_ACTION",
        "approval_required": False,
        "approval_status": "approved",
        "user_query": "Execute approved candidate action."
    }
    
    try:
        final_state = agent_graph.invoke(update_state, config=config)
        return {
            "thread_id": thread_id,
            "intent": final_state.get("intent", "HR_ACTION"),
            "response": final_state.get("final_response", ""),
            "approval_required": False,
            "approval_status": "approved",
            "activity_logs": final_state.get("activity_logs", [])
        }
    except Exception as e:
        logger.error(f"Error approving agent action: {e}")
        raise HTTPException(status_code=500, detail=f"Approval execution error: {e}")

@router.post("/reject", response_model=AgentChatResponse)
async def agent_reject(req: AgentRejectRequest, current_user: dict = Depends(get_current_user)):
    """Cancels paused agent workflow after Human HR Rejection."""
    thread_id = req.thread_id
    logger.info(f"Agent Action REJECTED by HR user '{current_user['username']}' [thread_id: {thread_id}]")
    
    config = {"configurable": {"thread_id": thread_id}}
    update_state = {
        "intent": "HR_ACTION",
        "approval_required": False,
        "approval_status": "rejected",
        "user_query": "Cancel rejected action."
    }
    
    try:
        final_state = agent_graph.invoke(update_state, config=config)
        return {
            "thread_id": thread_id,
            "intent": final_state.get("intent", "HR_ACTION"),
            "response": final_state.get("final_response", "Action rejected by user."),
            "approval_required": False,
            "approval_status": "rejected",
            "activity_logs": final_state.get("activity_logs", [])
        }
    except Exception as e:
        logger.error(f"Error rejecting agent action: {e}")
        raise HTTPException(status_code=500, detail=f"Rejection execution error: {e}")

@router.get("/status/{thread_id}")
async def agent_status(thread_id: str, current_user: dict = Depends(get_current_user)):
    """Fetches current agent state & activity logs for thread_id."""
    config = {"configurable": {"thread_id": thread_id}}
    try:
        state_snapshot = agent_graph.get_state(config)
        if not state_snapshot or not state_snapshot.values:
            return {"thread_id": thread_id, "status": "empty"}
            
        values = state_snapshot.values
        return {
            "thread_id": thread_id,
            "intent": values.get("intent"),
            "approval_required": values.get("approval_required"),
            "approval_status": values.get("approval_status"),
            "activity_logs": values.get("activity_logs", [])
        }
    except Exception as e:
        logger.error(f"Error fetching agent status: {e}")
        raise HTTPException(status_code=500, detail=str(e))
