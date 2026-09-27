from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class AgentChatRequest(BaseModel):
    prompt: str = Field(..., description="User prompt to Agent")
    thread_id: Optional[str] = Field(default="thread_default", description="Conversation session thread ID")
    job_id: Optional[str] = Field(default="default_job_001")
    candidate_id: Optional[str] = Field(default=None)

class AgentApproveRequest(BaseModel):
    thread_id: str = Field(..., description="Target thread ID to approve")

class AgentRejectRequest(BaseModel):
    thread_id: str = Field(..., description="Target thread ID to reject")

class AgentChatResponse(BaseModel):
    thread_id: str
    intent: str
    response: str
    approval_required: bool
    approval_status: str
    activity_logs: List[Dict[str, Any]]
